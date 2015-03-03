from __future__ import unicode_literals

from indico_outlook.models.blacklist import OutlookBlacklistUser


def check_config():
    """Checks if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'username', 'password'))


def get_participating_users(event):
    """Returns participating users of an event who did not disable calendar updates."""
    users = set()
    for participant in event.getParticipation().getParticipantList():
        avatar = participant.getAvatar()
        if avatar and participant.getStatus() in {'added', 'accepted'}:
            users.add(avatar)
    for registrant in event.getRegistrantsList():
        avatar = registrant.getAvatar()
        if avatar:
            users.add(avatar)
    if users:
        # Remove users who disabled calendar updates
        blacklist = OutlookBlacklistUser.find_all(OutlookBlacklistUser.user_id.in_(
            int(u.id) for u in users if str(u.id).isdigit()))
        blacklist = {x.user_id for x in blacklist}
        users = {u for u in users if (not str(u.id).isdigit() or int(u.id) not in blacklist)}
    return users
