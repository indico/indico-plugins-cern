from __future__ import unicode_literals

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import joinedload

from indico.core.db import db
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.users import UserSetting


def check_config():
    """Checks if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'username', 'password'))


def get_participating_users(event):
    """Returns participating users of an event who did not disable calendar updates."""
    registrations = (Registration.query
                     .filter(Registration.is_active,
                             ~RegistrationForm.is_deleted,
                             Registration.user_id.isnot(None),
                             RegistrationForm.event_id == event.id)
                     .filter(~UserSetting.query
                             .filter(UserSetting.user_id == Registration.user_id,
                                     UserSetting.module == 'plugin_outlook',
                                     UserSetting.name == 'enabled',
                                     db.func.cast(UserSetting.value, JSONB) == db.func.cast(db.func.to_json(False),
                                                                                            JSONB))
                             .correlate(Registration)
                             .exists())
                     .join(Registration.registration_form)
                     .options(joinedload(Registration.user)))
    return {reg.user for reg in registrations}


def latest_actions_only(items, action_key_func):
    """Keeps only the most recent occurrence of each action, while preserving the order"""
    used = set()
    res = []
    for item in reversed(items):
        key = action_key_func(item)
        if key not in used:
            res.append(item)
            used.add(key)
    return reversed(res)
