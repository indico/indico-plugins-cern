from __future__ import unicode_literals

from operator import attrgetter

import requests
from requests import RequestException

from indico.core.db.util import run_after_commit
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.util.user import retrieve_principals
from MaKaC.webinterface.common.contribFilters import PosterFilterField

from indico_requests_audiovisual import SERVICES


def is_av_manager(user):
    """Checks if a user is an AV manager"""
    from indico_requests_audiovisual.plugin import AVRequestsPlugin
    principals = retrieve_principals(AVRequestsPlugin.settings.get('managers'))
    return any(principal.containsUser(user) for principal in principals)


def get_av_capable_rooms():
    """Returns a list of rooms with AV equipment"""
    eq_types = EquipmentType.find_all(EquipmentType.name == 'Webcast/Recording', Location.name == 'CERN',
                                      _join=EquipmentType.location)
    return set(Room.find_with_filters({'available_equipment': eq_types}))


def get_contributions(event):
    """Returns a list of contributions in rooms with AV equipment

    :return: a list of ``(contribution, capable, custom_room)`` tuples
    """
    not_poster = PosterFilterField(event, False, False)
    contribs = [cont for cont in event.getContributionList() if not_poster.satisfies(cont)]
    contribs = sorted(contribs, key=attrgetter('startDate'))
    av_capable_rooms = {r.name for r in get_av_capable_rooms()}
    event_room = event.getRoom() and event.getRoom().getName()
    return [(c,
             (c.getLocation() and c.getLocation().getName() == 'CERN' and
              c.getRoom() and c.getRoom().getName() in av_capable_rooms),
             (c.getRoom().getName() if c.getRoom() and c.getRoom().getName() != event_room else None))
            for c in contribs]


def get_selected_contributions(req):
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


def get_selected_services(req):
    """Gets the selected services

    :return: list of service names
    """
    return [SERVICES.get(s, s) for s in req.data['services']]


def has_capable_contributions(event):
    """Checks if there are any contributions in AV-capable rooms"""
    if event.getType() == 'simple_event':
        av_capable_rooms = {r.name for r in get_av_capable_rooms()}
        return event.getRoom() and event.getRoom().getName() in av_capable_rooms
    else:
        return any(capable for _, capable, _ in get_contributions(event))


def has_any_contributions(event):
    """Checks if there are any contributions in the event"""
    if event.getType() == 'simple_event':
        # a lecture is basically a contribution on its own
        return True
    else:
        return bool(get_contributions(event))


@run_after_commit  # otherwise the remote side might read old data
def send_webcast_ping():
    """Sends a ping notification when a webcast request changes"""
    from indico_requests_audiovisual.plugin import AVRequestsPlugin
    url = AVRequestsPlugin.settings.get('webcast_ping_url')
    if not url:
        return
    AVRequestsPlugin.logger.info('Sending webcast ping to {}'.format(url))
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
    except RequestException:
        AVRequestsPlugin.logger.exception('Could not send webcast ping')
