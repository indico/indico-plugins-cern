# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from pprint import pformat

import requests
from markupsafe import Markup
from requests.exceptions import RequestException, Timeout
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import MultiDict

from indico.core import signals
from indico.core.db import db
from indico.util.signals import values_from_signal
from indico.util.string import strip_control_chars

from indico_outlook.models.queue import OutlookAction, OutlookQueueEntry
from indico_outlook.util import check_config, is_event_excluded


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
        # entry_list is grouped by user+event
        for entry_list in entries.listvalues():
            entry_ids = {x.id for x in entry_list}
            seen = set()
            todo = []
            # pick the latest entry for each action
            for entry in reversed(entry_list):
                if entry.action in seen:
                    continue
                seen.add(entry.action)
                if is_event_excluded(entry.event):
                    continue
                todo.append(entry)
            # execute those entries in the original order, so cases like
            # "add, update, delete, add, update, update" are correctly
            # handled as "delete, add, update" to handle edge cases where
            # someone was removed from the registration and added back
            # without processing entries in between
            for entry in reversed(todo):
                if not _update_calendar_entry(entry, settings):
                    entry_ids.remove(entry.id)
            # record all ids which didn't fail for deletion
            delete_ids |= entry_ids
    finally:
        if delete_ids:
            OutlookQueueEntry.query.filter(OutlookQueueEntry.id.in_(delete_ids)).delete(synchronize_session=False)
            db.session.commit()


def _get_status(user, event, settings):
    from indico_outlook.plugin import OutlookPlugin
    status = OutlookPlugin.user_settings.get(user, 'status', settings['status'])
    for override in OutlookPlugin.user_settings.get(user, 'overrides'):
        if override['type'] == 'category' and override['id'] == event.category_id:
            # we don't keep going for a specific category id match
            return override['status']
        elif override['type'] == 'category_tree' and override['id'] in event.category_chain:
            # for category tree matches we keep going in case there's a specific match later.
            # we don't try to see which one is more specific because that'd be overkill!
            status = override['status']
    return status


def _get_reminder(user, event, settings):
    from indico_outlook.plugin import OutlookPlugin
    reminder = OutlookPlugin.user_settings.get(user, 'reminder', settings['reminder'])
    reminder_minutes = OutlookPlugin.user_settings.get(user, 'reminder_minutes', settings['reminder_minutes'])
    for override in OutlookPlugin.user_settings.get(user, 'overrides'):
        if override['type'] == 'category' and override['id'] == event.category_id:
            # we don't keep going for a specific category id match
            return override.get('reminder', reminder), override.get('reminder_minutes', reminder_minutes)
        elif override['type'] == 'category_tree' and override['id'] in event.category_chain:
            # for category tree matches we keep going in case there's a specific match later.
            # we don't try to see which one is more specific becauase that'd be overkill!
            reminder = override.get('reminder', reminder), override.get('reminder_minutes', reminder_minutes)
    return reminder, reminder_minutes


def _update_calendar_entry(entry, settings):
    """Executes a single calendar update

    :param entry: a :class:`OutlookQueueEntry`
    :param settings: the plugin settings
    """
    from indico_outlook.plugin import OutlookPlugin
    logger = OutlookPlugin.logger

    logger.info('Processing %s', entry)
    user = entry.user
    if user is None:
        logger.debug('Ignoring %s for deleted user %s', entry.action.name, entry.user_id)
        return True
    elif not OutlookPlugin.user_settings.get(user, 'enabled'):
        logger.debug('User %s has disabled calendar entries', user)
        return True

    unique_id = '{}{}_{}'.format(settings['id_prefix'], user.id, entry.event_id)
    path = f'/api/v1/users/{user.email}/events/{unique_id}'
    url = settings['service_url'].rstrip('/') + path
    if entry.action in {OutlookAction.add, OutlookAction.update}:
        method = 'PUT'
        event = entry.event
        if event.is_deleted:
            logger.debug('Ignoring %s for deleted event %s', entry.action.name, entry.event_id)
            return True
        reminder, reminder_minutes = _get_reminder(user, event, settings)
        location = (f'{event.room_name} ({event.venue_name})'
                    if event.venue_name and event.room_name
                    else (event.venue_name or event.room_name))

        cal_description = []
        if event.person_links:
            speakers = [f'{x.full_name} ({x.affiliation})' if x.affiliation else x.full_name
                        for x in event.person_links]
            cal_description.append(Markup('<p>Speakers: {}</p>').format(', '.join(speakers)))
        cal_description.append(event.description)
        cal_description.append(f'<p><a href="{event.external_url}">{event.external_url}</a></p>')

        data = {
            'status': _get_status(user, event, settings),
            'start': int(event.start_dt.timestamp()),
            'end': int(event.end_dt.timestamp()),
            'subject': strip_control_chars(event.title),
            # XXX: the API expects 'body', we convert it below
            'description': strip_control_chars('\n<br>\n'.join(cal_description)),
            'location': strip_control_chars(location),
            'reminder_on': reminder,
            'reminder_minutes': reminder_minutes,
        }

        # check whether the plugins want to add/override any data
        for update in values_from_signal(
            signals.event.metadata_postprocess.send('ical-export', event=event, data=data, user=user,
                                                    html_fields={'description'}),
            as_list=True
        ):
            data.update(update)
        # the API expects the field to be named 'body', contrarily to our usage
        data['body'] = data.pop('description')
    elif entry.action == OutlookAction.remove:
        method = 'DELETE'
        data = None
    else:
        raise ValueError(f'Unexpected action: {entry.action}')

    if settings['debug']:
        logger.debug('Calendar update request:\nURL: %s\nData: %s', url, pformat(data))
        return True

    token = settings['token']
    try:
        res = requests.request(method, url, json=data, headers={'Authorization': f'Bearer {token}'},
                               timeout=settings['timeout'])
    except Timeout:
        logger.warning('Request timed out')
        return False
    except RequestException:
        logger.exception('Request failed:\nURL: %s\nData: %s', url, pformat(data))
        return False
    else:
        logger.info('Request to %s %s finished with status %r and body %r', method, path, res.status_code, res.text)
        # 404 is "already deleted" or "user has no mailbox" - both cases we consider a success
        if res.ok or res.status_code == 404:
            return True
        logger.error('Request unsuccessful:\nURL: %s\nData: %s\nCode: %s\nResponse: %s',
                     url, pformat(data), res.status_code, res.text)
        return False
