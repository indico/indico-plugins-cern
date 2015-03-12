from __future__ import unicode_literals

import posixpath
import pytz
from pprint import pformat

import requests
from flask_pluginengine import current_plugin
from requests.exceptions import Timeout, RequestException
from werkzeug.datastructures import MultiDict

from indico.core.db import db
from indico.modules.scheduler.tasks.periodic import PeriodicUniqueTask
from indico.util.date_time import format_datetime
from indico.util.string import strip_control_chars, to_unicode

from indico_outlook.models.blacklist import OutlookBlacklistUser
from indico_outlook.models.queue import OutlookQueueEntry, OutlookAction
from indico_outlook.util import check_config


operation_map = {
    OutlookAction.add: 'CreateEventInCalendar',
    OutlookAction.update: 'UpdateExistingEventInCalendar',
    OutlookAction.remove: 'DeleteEventInCalendar'
}


def _latest_actions_only(items):
    # Keeps only the most recent occurrence of each action, while preserving the order
    used = set()
    res = []
    for item in reversed(items):
        if item.action not in used:
            res.append(item)
            used.add(item.action)
    return reversed(res)


def update_calendar(logger=None):
    """Executes all pending calendar updates

    :param logger: the :class:`~indico.core.logger.Logger` to use; if
                   None, the plugin logger is used
    """
    from indico_outlook.plugin import OutlookPlugin

    if logger is None:
        logger = current_plugin.logger

    if not check_config():
        logger.error('Plugin is not configured properly')
        return

    settings = OutlookPlugin.settings.get_all()
    query = OutlookQueueEntry.find().order_by(OutlookQueueEntry.user_id, OutlookQueueEntry.id)
    entries = MultiDict((entry.user_id, entry) for entry in query)
    delete_ids = set()
    try:
        for user_id, user_entries in entries.iterlists():
            user_entry_ids = {x.id for x in user_entries}
            for entry in _latest_actions_only(user_entries):
                if not _update_calendar_entry(logger, entry, settings):
                    user_entry_ids.remove(entry.id)
            # record all ids which didn't fail for deletion
            delete_ids |= user_entry_ids
    finally:
        if delete_ids:
            OutlookQueueEntry.find(OutlookQueueEntry.id.in_(delete_ids)).delete(synchronize_session='fetch')
            db.session.commit()


def _update_calendar_entry(logger, entry, settings):
    """Executes a single calendar update

    :param logger: the logger to use
    :param entry: a :class:`OutlookQueueEntry`
    :param settings: the plugin settings
    """
    logger.info('Processing {}'.format(entry))
    url = posixpath.join(settings['service_url'], operation_map[entry.action])
    user = entry.user
    if user is None:
        logger.debug('Ignoring {} for deleted user {}'.format(entry.action.name, entry.user_id))
        return True
    email = to_unicode(user.email)
    unique_id = '{}{}_{}'.format(settings['id_prefix'], user.id, entry.event_id)

    if OutlookBlacklistUser.find_first(user_id=int(user.id)):
        logger.debug('User {} has disabled calendar entries'.format(user.id))
        return True

    if entry.action in {OutlookAction.add, OutlookAction.update}:
        event = entry.event
        if event is None:
            logger.debug('Ignoring {} for deleted event {}'.format(entry.action.name, entry.event_id))
            return True
        location = strip_control_chars(event.getRoom().getName()) if event.getRoom() else ''
        description = to_unicode(strip_control_chars(event.description))
        event_url = to_unicode(event.getURL())
        data = {'userEmail': email,
                'uniqueID': unique_id,
                'subject': to_unicode(strip_control_chars(event.title)),
                'location': location,
                'body': '<a href="{}">{}</a><br><br>{}'.format(event_url, event_url, description),
                'status': settings['status'],
                'startDate': format_datetime(event.getStartDate(), format='MM-dd-yyyy HH:mm', timezone=pytz.utc),
                'endDate': format_datetime(event.getEndDate(), format='MM-dd-yyyy HH:mm', timezone=pytz.utc),
                'isThereReminder': settings['reminder'],
                'reminderTimeInMinutes': settings['reminder_minutes']}
    elif entry.action == OutlookAction.remove:
        data = {'userEmail': email,
                'uniqueID': unique_id}
    else:
        raise ValueError('Unexpected action: {}'.format(entry.action))

    if settings['debug']:
        logger.debug('Calendar update request:\nURL: {}\nData: {}'.format(url, pformat(data)))
        return True

    try:
        res = requests.post(url, data, auth=(settings['username'], settings['password']),
                            timeout=settings['timeout'],
                            headers={'Content-Type': 'application/x-www-form-urlencoded'})
    except Timeout:
        logger.warning('Request timed out')
        return False
    except RequestException:
        logger.exception('Request failed:\nURL: {}\nData: {}'.format(url, pformat(data)))
        return False
    else:
        if res.status_code == 200:
            return True
        logger.error('Request unsuccessful:\nURL: {}\nData: {}\nCode: {}\nResponse: {}'.format(url, pformat(data),
                                                                                               res.status_code,
                                                                                               res.text))
        return False


class OutlookTask(PeriodicUniqueTask):
    DISABLE_ZODB_HOOK = True

    def run(self):
        from indico_outlook.plugin import OutlookPlugin

        plugin = OutlookPlugin.instance  # RuntimeError if not active
        with plugin.plugin_context():
            update_calendar(self.getLogger())
