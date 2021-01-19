# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import posixpath
from pprint import pformat

import pytz
import requests
from requests.exceptions import RequestException, Timeout
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import MultiDict

from indico.core.db import db
from indico.util.date_time import format_datetime
from indico.util.string import strip_control_chars

from indico_outlook.models.queue import OutlookAction, OutlookQueueEntry
from indico_outlook.util import check_config, is_event_excluded, latest_actions_only


operation_map = {
    OutlookAction.add: 'CreateEventInCalendar',
    OutlookAction.update: 'UpdateExistingEventInCalendar',
    OutlookAction.remove: 'DeleteEventInCalendar'
}


def update_calendar():
    """Executes all pending calendar updates"""
    from indico_outlook.plugin import OutlookPlugin

    if not check_config():
        OutlookPlugin.logger.error('Plugin is not configured properly')
        return

    settings = OutlookPlugin.settings.get_all()
    query = (OutlookQueueEntry.query
             .options(joinedload(OutlookQueueEntry.event))
             .order_by(OutlookQueueEntry.user_id, OutlookQueueEntry.id))
    entries = MultiDict(((entry.user_id, entry.event_id), entry) for entry in query)
    delete_ids = set()
    try:
        for (user_id, event_id), entry_list in entries.lists():
            entry_ids = {x.id for x in entry_list}
            for entry in latest_actions_only(entry_list):
                if is_event_excluded(entry.event):
                    continue
                if not _update_calendar_entry(entry, settings):
                    entry_ids.remove(entry.id)
            # record all ids which didn't fail for deletion
            delete_ids |= entry_ids
    finally:
        if delete_ids:
            OutlookQueueEntry.query.filter(OutlookQueueEntry.id.in_(delete_ids)).delete(synchronize_session=False)
            db.session.commit()


def _update_calendar_entry(entry, settings):
    """Executes a single calendar update

    :param entry: a :class:`OutlookQueueEntry`
    :param settings: the plugin settings
    """
    from indico_outlook.plugin import OutlookPlugin
    logger = OutlookPlugin.logger

    logger.info('Processing %s', entry)
    url = posixpath.join(settings['service_url'], operation_map[entry.action])
    user = entry.user
    if user is None:
        logger.debug('Ignoring %s for deleted user %s', entry.action.name, entry.user_id)
        return True
    elif not OutlookPlugin.user_settings.get(user, 'enabled'):
        logger.debug('User %s has disabled calendar entries', user)
        return True

    unique_id = '{}{}_{}'.format(settings['id_prefix'], user.id, entry.event_id)
    if entry.action in {OutlookAction.add, OutlookAction.update}:
        event = entry.event
        if event.is_deleted:
            logger.debug('Ignoring %s for deleted event %s', entry.action.name, entry.event_id)
            return True
        location = strip_control_chars(event.room_name)
        description = strip_control_chars(event.description)
        event_url = event.external_url
        data = {'userEmail': user.email,
                'uniqueID': unique_id,
                'subject': strip_control_chars(event.title),
                'location': location,
                'body': f'<a href="{event_url}">{event_url}</a><br><br>{description}',
                'status': OutlookPlugin.user_settings.get(user, 'status', settings['status']),
                'startDate': format_datetime(event.start_dt, format='MM-dd-yyyy HH:mm', timezone=pytz.utc),
                'endDate': format_datetime(event.end_dt, format='MM-dd-yyyy HH:mm', timezone=pytz.utc),
                'isThereReminder': settings['reminder'],
                'reminderTimeInMinutes': settings['reminder_minutes']}
    elif entry.action == OutlookAction.remove:
        data = {'userEmail': user.email,
                'uniqueID': unique_id}
    else:
        raise ValueError(f'Unexpected action: {entry.action}')

    if settings['debug']:
        logger.debug('Calendar update request:\nURL: %s\nData: %s', url, pformat(data))
        return True

    try:
        res = requests.post(url, data, auth=(settings['username'], settings['password']),
                            timeout=settings['timeout'],
                            headers={'Content-Type': 'application/x-www-form-urlencoded'})
    except Timeout:
        logger.warning('Request timed out')
        return False
    except RequestException:
        logger.exception('Request failed:\nURL: %s\nData: %s', url, pformat(data))
        return False
    else:
        if res.status_code == 200:
            return True
        logger.error('Request unsuccessful:\nURL: %s\nData: %s\nCode: %s\nResponse: %s',
                     url, pformat(data), res.status_code, res.text)
        return False
