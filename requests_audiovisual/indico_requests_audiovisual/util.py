from __future__ import unicode_literals

from operator import attrgetter

from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.util.user import retrieve_principals
from MaKaC.webinterface.common.contribFilters import PosterFilterField


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
