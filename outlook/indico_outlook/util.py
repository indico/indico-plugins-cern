# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from sqlalchemy.orm import joinedload

from indico.core.db import db
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.users import UserSetting
from indico.util.date_time import now_utc


def check_config():
    """Check if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'token'))


def is_event_excluded(event):
    """Check if an event is excluded from the calendar"""
    from indico_outlook.plugin import OutlookPlugin
    return event.duration > OutlookPlugin.settings.get('max_event_duration') or event.end_dt <= now_utc()


def get_registered_users(event):
    """Return participating users of an event who did not disable calendar updates."""
    registrations = (Registration.query
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
                     .join(Registration.registration_form)
                     .options(joinedload(Registration.user)))
    return {reg.user for reg in registrations}


def latest_actions_only(items):
    """Keep only the most recent occurrence of each action, while preserving the order"""
    used = set()
    res = []
    for item in reversed(items):
        if item not in used:
            res.append(item)
            used.add(item)
    return reversed(res)
