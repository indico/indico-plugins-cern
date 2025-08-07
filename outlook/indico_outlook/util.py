# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from sqlalchemy.orm import joinedload

from indico.cli.event import User
from indico.core.db import db
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.users import UserSetting
from indico.modules.users.models.favorites import favorite_event_table
from indico.util.date_time import now_utc

from indico_outlook.models.entry import OutlookCalendarEntry


def check_config():
    """Check if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'token'))


def is_event_excluded(event, logger=None):
    """Check if an event is excluded from the calendar"""
    from indico_outlook.plugin import OutlookPlugin
    if event.duration > OutlookPlugin.settings.get('max_event_duration'):
        if logger:
            logger.debug('Ignoring overly long event')
        return True
    if event.end_dt <= now_utc():
        if logger:
            logger.debug('Ignoring past event')
        return True
    return False


def _query_registered_users(event):
    return (Registration.query
            .filter(Registration.is_active,
                    ~RegistrationForm.is_deleted,
                    Registration.user_id.isnot(None),
                    RegistrationForm.event_id == event.id)
            .filter(~UserSetting.query
                    .filter(UserSetting.user_id == Registration.user_id,
                            UserSetting.module == 'plugin_outlook',
                            UserSetting.name == 'enabled',
                            UserSetting.value == db.func.to_jsonb(False))
                    .correlate(Registration)
                    .exists())
            .filter(~UserSetting.query
                    .filter(UserSetting.user_id == Registration.user_id,
                            UserSetting.module == 'plugin_outlook',
                            UserSetting.name == 'registered',
                            UserSetting.value == db.func.to_jsonb(False))
                    .correlate(Registration)
                    .exists())
            .join(Registration.registration_form)
            .options(joinedload(Registration.user)))


def is_user_registered(event, user):
    """Check if the user is registered in the event and wants it in their calendar."""
    return _query_registered_users(event).filter(Registration.user == user).has_rows()


def get_registered_users(event):
    """Return participating users of an event who did not disable calendar updates."""
    return {reg.user for reg in _query_registered_users(event)}


def _query_favorite_users(event):
    return (User.query
            .join(favorite_event_table, favorite_event_table.c.user_id == User.id)
            .filter(favorite_event_table.c.target_id == event.id)
            .filter(~UserSetting.query
                    .filter(UserSetting.user_id == User.id,
                            UserSetting.module == 'plugin_outlook',
                            UserSetting.name == 'enabled',
                            UserSetting.value == db.func.to_jsonb(False))
                    .correlate(User)
                    .exists())
            .filter(~UserSetting.query
                    .filter(UserSetting.user_id == User.id,
                            UserSetting.module == 'plugin_outlook',
                            UserSetting.name == 'favorite_events',
                            UserSetting.value == db.func.to_jsonb(False))
                    .correlate(User)
                    .exists()))


def is_user_favorite(event, user):
    """Check if the user favorited the event and wants it in their calendar."""
    return _query_favorite_users(event).filter(User.id == user.id).has_rows()


def get_favorite_users(event):
    """Return users who favorited an event and did not disable calendar updates."""
    return set(_query_favorite_users(event))


def _iter_visible_categories(event):
    if event.visibility == 0:
        return
    horizon = event.category.real_visibility_horizon
    for i, cat in enumerate(reversed(event.category.chain_query.all()), 1):
        yield cat
        # Stop if we reach the visibility horizon of the event
        if i == event.visibility:
            return
        # Stop if we reach the visibility horizon of the category
        if cat == horizon:
            return


def is_user_cat_favorite(event, user):
    """Check if the event is in a favorite category of the user and tracks favorite categories."""
    from indico_outlook.plugin import OutlookPlugin
    if not OutlookPlugin.user_settings.get(user, 'favorite_categories'):
        return False
    if event.is_unlisted:
        return False
    return any(cat in user.favorite_categories for cat in _iter_visible_categories(event))


def get_cat_favorite_users(event):
    """Return users who have the event in a favorite category and did not disable calendar updates."""
    from indico_outlook.plugin import OutlookPlugin
    plugin = OutlookPlugin.instance
    if event.is_unlisted:
        return set()
    return {
        user
        for cat in _iter_visible_categories(event)
        for user in cat.favorite_of
        if plugin._user_tracks_favorite_categories(user) and event.can_access(user, allow_admin=False)
    }


def get_users_to_add(event):
    """Get users who should have the event in their calendar but currently don't have it."""
    users_to_add = set()
    users_to_add |= get_registered_users(event)
    users_to_add |= get_favorite_users(event)
    users_to_add |= get_cat_favorite_users(event)
    # Skip users who already have calendar entries
    existing_users = {x.user for x in event.outlook_calendar_entries.options(joinedload(OutlookCalendarEntry.user))}
    return users_to_add - existing_users


def latest_actions_only(items):
    """Keep only the most recent occurrence of each action, while preserving the order"""
    used = set()
    res = []
    for item in reversed(items):
        if item not in used:
            res.append(item)
            used.add(item)
    return reversed(res)
