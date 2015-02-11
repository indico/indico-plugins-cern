from __future__ import unicode_literals

from flask_pluginengine import current_plugin

from indico.modules.events.requests import RequestDefinitionBase
from indico.util.i18n import _

from indico_requests_audiovisual import SERVICES
from indico_requests_audiovisual.forms import AVRequestForm
from indico_requests_audiovisual.util import is_av_manager, get_contributions, get_av_capable_rooms


class AVRequest(RequestDefinitionBase):
    name = 'webcast-recording'
    title = _('Webcast / Recording')
    form = AVRequestForm
    form_defaults = {'all_contributions': True}

    @classmethod
    def can_be_managed(cls, user):
        return user.isAdmin() or is_av_manager(user)

    @classmethod
    def get_manager_notification_emails(cls):
        return set(current_plugin.settings.get('notification_emails'))

    @classmethod
    def get_selected_contributions(cls, req):
        """Gets the selected contributions for a request.

        :return: list of ``(contribution, capable, custom_room)`` tuples
        """
        if req.event.getType() == 'simple_event':
            return []
        contributions = get_contributions(req.event)
        if not req.data.get('all_contributions', True):
            selected = set(req.data['contributions'])
            contributions = [x for x in contributions if x[0].id in selected]
        return contributions

    @classmethod
    def get_selected_services(cls, req):
        """Gets the selected services

        :return: list of service names
        """
        return [SERVICES.get(s, s) for s in req.data['services']]

    @classmethod
    def has_capable_contributions(cls, event):
        """Checks if there are any contributions in AV-capable rooms"""
        if event.getType() == 'simple_event':
            av_capable_rooms = {r.name for r in get_av_capable_rooms()}
            return event.getRoom() and event.getRoom().getName() in av_capable_rooms
        else:
            return any(capable for _, capable, _ in get_contributions(event))

    @classmethod
    def has_any_contributions(cls, event):
        """Checks if there are any contributions in the event"""
        if event.getType() == 'simple_event':
            # a lecture is basically a contribution on its own
            return True
        else:
            return bool(get_contributions(event))

    @classmethod
    def get_capable_rooms(cls):
        """Returns the list of AV-capable rooms"""
        return get_av_capable_rooms()
