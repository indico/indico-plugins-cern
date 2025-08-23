# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import defaultdict
from itertools import islice
from pprint import pformat

import requests
from markupsafe import Markup
from requests.exceptions import RequestException, Timeout
from sqlalchemy.orm import joinedload, subqueryload
from werkzeug.datastructures import MultiDict

from indico.core import signals
from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.forms import EventLabel
from indico.util.date_time import now_utc
from indico.util.signals import values_from_signal
from indico.util.string import strip_control_chars

from indico_outlook.models.entry import OutlookCalendarEntry
from indico_outlook.models.queue import OutlookAction, OutlookQueueEntry
from indico_outlook.util import (check_config, get_users_to_add, is_event_excluded, is_user_cat_favorite,
                                 is_user_favorite, is_user_registered)


def update_calendar():
    """Executes all pending calendar updates"""
    from indico_outlook.plugin import OutlookPlugin

    if not check_config():
        OutlookPlugin.logger.error('Plugin is not configured properly')
        return

    settings = OutlookPlugin.settings.get_all()
    logger = OutlookPlugin.logger
    ignore = _process_favorite_categories(settings, logger)
    _process_events(ignore, settings, logger)


def _delete_queue_entries(ids):
    if not ids:
        return
    OutlookQueueEntry.query.filter(OutlookQueueEntry.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()


def _process_favorite_categories(settings, logger):
    # process the category queue
    query = (OutlookQueueEntry.query
             .options(joinedload(OutlookQueueEntry.category))
             .order_by(OutlookQueueEntry.user_id, OutlookQueueEntry.id)
             .filter(OutlookQueueEntry.category_id.isnot(None)))
    by_category = {}
    delete_ids = set()
    for entry in query:
        if (
            (existing := by_category.get(entry.category))
            and existing.action == OutlookAction.add
            and entry.action == OutlookAction.remove
        ):
            # add + remove --> ignore both and do nothing; this was someone adding and immediately
            # removing a favorite category.
            # we don't do the same for remove + add, because someone may use this after turning on
            # this feature for favorite categories and toggling the favorite state of a category to
            # force new events in there to be added
            logger.debug('Ignoring add+remove for category %r / user %r', entry.category, entry.user)
            delete_ids.add(existing.id)
            delete_ids.add(entry.id)
            del by_category[entry.category]
            continue
        by_category[entry.category] = entry

    if delete_ids:
        _delete_queue_entries(delete_ids)
        delete_ids.clear()

    by_user = defaultdict(set)
    for entry in by_category.values():
        by_user[entry.user].add(entry)

    ignore = set()
    for user, entries in by_user.items():
        delete_cat_entries = {x for x in entries if x.action == OutlookAction.remove}
        add_cat_entries = {(x.category, x) for x in entries if x.action == OutlookAction.add}
        del entries

        if delete_cat_entries:
            logger.debug('Processing category favorite removals for %r', user)
            # deletion is an easy case, we can simply get all future events within the deleted
            # category subtrees where the user has a calendar entry, unless it's also visible
            # in another favorite category...
            events = Event.query.filter(
                Event.end_dt > now_utc(),
                ~Event.is_deleted,
                Event.category_chain_overlaps({x.category_id for x in delete_cat_entries}),
                Event.outlook_calendar_entries.any(OutlookCalendarEntry.user == user),
            ).all()
            success = True
            for event in events:
                if is_user_registered(event, user):
                    logger.debug('Ignoring remove for %r; user is registered', event)
                    continue
                if is_user_favorite(event, user):
                    logger.debug('Ignoring remove for %r; event is favorite', event)
                    continue
                if is_user_cat_favorite(event, user):
                    logger.debug('Ignoring remove for %r; event is cat favorite', event)
                    continue
                logger.info('Removing event %r', event)
                if not _update_calendar_entry(event, user, OutlookAction.remove, settings):
                    success = False
                else:
                    ignore.add((event, user))

            if success:
                _delete_queue_entries({x.id for x in delete_cat_entries})

        for cat, entry in add_cat_entries:
            logger.info('Processing category favorite addition for %r: %r', user, cat)
            query = (
                Event.query.filter(
                    Event.end_dt > now_utc(),
                    Event.duration <= settings['max_event_duration'],
                    ~Event.is_deleted,
                    Event.is_visible_in(cat.id),
                    ~Event.label.has(EventLabel.is_event_not_happening),
                    ~Event.outlook_calendar_entries.any(OutlookCalendarEntry.user == user),
                )
                .options(subqueryload('acl_entries'))
                .order_by(Event.start_dt, Event.id)
            )
            total_limit = settings['max_category_events']
            limit = settings['max_accessible_category_events']
            # bail out early if it's a ridiculously big category (e.g. root category)
            if (count := query.count()) > total_limit:
                logger.info('Ignoring favorite category %r: too many future events (%d > %d)', cat, count,
                            total_limit)
                delete_ids.add(entry.id)
                continue
            # get the events which the user can actually access
            events = list(islice((e for e in query if e.can_access(user, allow_admin=False)), limit + 1))
            if len(events) > limit:
                logger.info('Ignoring favorite category %r: too many accessible future events (%d > %d)', cat,
                            count, limit)
                delete_ids.add(entry.id)
                continue
            logger.info('Adding %d events visible in favorite category %r', count, cat)
            success = True
            for event in events:
                logger.info('Adding event %r', event)
                if not _update_calendar_entry(event, user, OutlookAction.add, settings):
                    success = False
                else:
                    ignore.add((event, user))
            if success:
                delete_ids.add(entry.id)
                _delete_queue_entries(delete_ids)
                delete_ids.clear()

        # skipped large category entries may not have been deleted yet
        if delete_ids:
            _delete_queue_entries(delete_ids)
            delete_ids.clear()

    return ignore


def _process_events(ignore, settings, logger):
    # process the event queue, including any changes we may have created due to category changes
    query = (OutlookQueueEntry.query
             .options(joinedload(OutlookQueueEntry.event))
             .order_by(OutlookQueueEntry.id)
             .filter(OutlookQueueEntry.event_id.isnot(None)))
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
                if (entry.event, entry.user) in ignore:
                    logger.debug('Ignoring %s due to favorite category change: %r', entry.action.name, entry)
                    continue
                todo.append(entry)
            # execute those entries in the original order, so cases like
            # "add, update, delete, add, update, update" are correctly
            # handled as "delete, add, update" to handle edge cases where
            # someone was removed from the registration and added back
            # without processing entries in between
            for entry in reversed(todo):
                logger.info('Processing %s', entry)
                if entry.user and not _update_calendar_entry(entry.event, entry.user, entry.action, settings):
                    entry_ids.remove(entry.id)
                elif not entry.user and not _update_bulk(entry.event, entry.action, settings):
                    entry_ids.remove(entry.id)
            # record all ids which didn't fail for deletion
            delete_ids |= entry_ids
    finally:
        _delete_queue_entries(delete_ids)


def _update_bulk(event, action, settings):
    if action in {OutlookAction.update, OutlookAction.remove}:
        success = True
        for cal_entry in event.outlook_calendar_entries:
            if not _update_calendar_entry(event, cal_entry.user, action, settings):
                success = False
        return success
    elif action == OutlookAction.add:
        success = True
        for user in get_users_to_add(event):
            if not _update_calendar_entry(event, user, action, settings):
                success = False
        return success


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
            reminder = override.get('reminder', reminder)
            reminder_minutes = override.get('reminder_minutes', reminder_minutes)
    return reminder, reminder_minutes


def _make_calendar_id(event, user, settings):
    if settings['event_id_cutoff'] != -1 and event.id > settings['event_id_cutoff']:
        return event.ical_uid
    return f'{settings["id_prefix"]}{user.id}_{event.id}'


def _update_calendar_entry(event, user, action, settings) -> bool:
    """Execute a single calendar update.

    :return: `True` if the related queue entry should be removed.
    """
    from indico_outlook.plugin import OutlookPlugin
    logger = OutlookPlugin.logger

    if not OutlookPlugin.user_settings.get(user, 'enabled'):
        logger.debug('User %s has disabled calendar entries', user)
        return True

    if existing := OutlookCalendarEntry.get(event, user):
        logger.debug('Found existing calendar entry in DB: %s', existing.calendar_entry_id)
    elif action == OutlookAction.update:
        logger.info('No calendar entry found in DB for event=%s/user=%s during update', event.id, user.id)
    elif action == OutlookAction.remove:
        logger.debug('No calendar entry found in DB for event=%s/user=%s, ignoring remove', event.id, user.id)
        return True

    # Use common format for event calendar ID if the event was created after the cutoff event
    unique_id = existing.calendar_entry_id if existing else _make_calendar_id(event, user, settings)
    path = f'/api/v1/users/{user.email}/events/{unique_id}'
    url = settings['service_url'].rstrip('/') + path
    if action in {OutlookAction.add, OutlookAction.update}:
        method = 'PUT'
        if event.is_deleted:
            logger.debug('Ignoring %s for deleted event %s', action.name, event.id)
            return True
        reminder, reminder_minutes = _get_reminder(user, event, settings)
        location = (f'{event.room_name} ({event.venue_name})'
                    if event.venue_name and event.room_name
                    else (event.venue_name or event.room_name))

        title = event.title
        if event.label:
            title = f'[{event.label.title}] {title}'

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
            'subject': strip_control_chars(title),
            # XXX: the API expects 'body', we convert it below
            'description': strip_control_chars('<br>\n'.join(cal_description)),
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
    elif action == OutlookAction.remove:
        method = 'DELETE'
        data = None
    else:
        raise ValueError(f'Unexpected action: {action}')

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
        if res.ok and not existing and action in {OutlookAction.add, OutlookAction.update}:
            # successfully added or updated w/ no reference to existing entry
            OutlookCalendarEntry.create(event, user, unique_id)
            logger.debug('Recorded calendar entry in DB')
            db.session.commit()
        elif (res.ok or res.status_code == 404) and action == OutlookAction.remove:
            # successfully removed or nothing to remove
            db.session.delete(existing)
            db.session.commit()
            logger.debug('Removed calendar entry from DB')
        elif res.status_code == 404 and action == OutlookAction.update and existing:
            # tried to update but nothing to update
            db.session.delete(existing)
            db.session.commit()
            logger.debug('Removed calendar entry from DB')
        # 404 is "already deleted" or "user has no mailbox" - both cases we consider a success
        if res.ok or res.status_code == 404:
            return True
        logger.error('Request unsuccessful:\nURL: %s\nData: %s\nCode: %s\nResponse: %s',
                     url, pformat(data), res.status_code, res.text)
        return False
