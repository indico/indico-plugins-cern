from __future__ import unicode_literals

from sqlalchemy.orm import joinedload

from indico.modules.users import UserSetting
from indico.util.event import unify_event_args


def check_config():
    """Checks if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'username', 'password'))


@unify_event_args(legacy=True)
def get_participating_users(event):
    """Returns participating users of an event who did not disable calendar updates."""
    users = set()
    for participant in event.getParticipation().getParticipantList():
        avatar = participant.getAvatar()
        if avatar and participant.getStatus() in {'added', 'accepted'} and avatar.user:
            users.add(avatar.user)
    for registrant in event.getRegistrantsList():
        avatar = registrant.getAvatar()
        if avatar and avatar.user:
            users.add(avatar.user)
    if users:
        # Remove users who disabled calendar updates
        query = (UserSetting.query
                 .options(joinedload(UserSetting.user))
                 .filter_by(module='plugin_outlook', name='enabled'))
        users -= {x.user for x in query if not x.value}
    return users


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
