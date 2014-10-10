from __future__ import unicode_literals

import posixpath
import pytz
from pprint import pformat

import requests
from requests.exceptions import Timeout, RequestException

from indico.core.db import db
from indico.core.logger import Logger
from indico.modules.scheduler.tasks.periodic import PeriodicUniqueTask
from indico.util.date_time import format_datetime
from indico.util.string import strip_control_chars, to_unicode

from indico_outlook.models.outlook_blacklist import OutlookBlacklistUser
from indico_outlook.models.outlook_queue import OutlookQueueEntry, OutlookAction
from indico_outlook.util import check_config


operation_map = {
    OutlookAction.add: 'CreateEventInCalendar',
    OutlookAction.update: 'UpdateExistingEventInCalendar',
    OutlookAction.remove: 'DeleteEventInCalendar'
}


def update_calendar(logger=None):
    """Executes all pending calendar updates

    :param logger: the :class:`~indico.core.logger.Logger` to use; if
                   None, the plugin logger is used
    """
    if logger is None:
        logger = Logger.get('plugin.outlook')

    if not check_config():
        logger.error('Plugin is not configured properly')
        return

    for entry in OutlookQueueEntry.find().order_by(OutlookQueueEntry.id).all():
        if _update_calendar_entry(logger, entry):
            db.session.delete(entry)
            db.session.commit()


def _update_calendar_entry(logger, entry):
    """Executes a single calendar update

    :param logger: the logger to use
    :param entry: a :class:`OutlookQueueEntry`
    """
    from indico_outlook.plugin import OutlookPlugin

    logger.info('Processing {}'.format(entry))
    settings = OutlookPlugin.settings.get_all()
    url = posixpath.join(settings['service_url'], operation_map[entry.action])
    event = entry.event
    user = entry.user
    email = to_unicode(user.email)
    unique_id = '{}{}_{}'.format(settings['id_prefix'], user.id, event.id)

    if OutlookBlacklistUser.find_first(user_id=int(user.id)):
        logger.debug('User {} has disabled calendar entries'.format(user.id))
        return True

    if entry.action in {OutlookAction.add, OutlookAction.update}:
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
