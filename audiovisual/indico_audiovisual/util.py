from __future__ import unicode_literals

import json
from itertools import chain

import requests

from indico.core.celery import celery
from indico.core.db.sqlalchemy.util.queries import limit_groups, db_dates_overlap
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.fulltextindexes.models.events import IndexedEvent
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.util.caching import memoize_request
from indico.util.date_time import overlaps
from MaKaC.conference import SubContribution
from MaKaC.webinterface.common.contribFilters import PosterFilterField

from indico_audiovisual import SERVICES


def is_av_manager(user):
    """Checks if a user is an AV manager"""
    from indico_audiovisual.plugin import AVRequestsPlugin
    if user.is_admin:
        return True
    return AVRequestsPlugin.settings.acls.contains_user('managers', user)


@memoize_request
def get_av_capable_rooms():
    """Returns a list of rooms with AV equipment"""
    eq_types = EquipmentType.find_all(EquipmentType.name == 'Webcast/Recording', Location.name == 'CERN',
                                      _join=EquipmentType.location)
    return set(Room.find_with_filters({'available_equipment': eq_types}))


def _contrib_key(contrib):
    # key function to sort contributions and their subcontributions properly
    is_subcontrib = isinstance(contrib, SubContribution)
    return (contrib.getContribution().startDate,
            contrib.getContribution().id,
            is_subcontrib,
            (contrib.getContribution().getSubContributionList().index(contrib) if is_subcontrib else None),
            contrib.getTitle())


def get_contributions(event):
    """Returns a list of contributions in rooms with AV equipment

    :return: a list of ``(contribution, capable, custom_room)`` tuples
    """
    from indico_audiovisual.plugin import AVRequestsPlugin
    not_poster = PosterFilterField(event, False, False)
    contribs = [cont for cont in event.getContributionList() if cont.startDate and not_poster.satisfies(cont)]
    if AVRequestsPlugin.settings.get('allow_subcontributions'):
        contribs.extend(list(chain.from_iterable(cont.getSubContributionList() for cont in contribs)))
    contribs = sorted(contribs, key=_contrib_key)
    av_capable_rooms = {r.name for r in get_av_capable_rooms()}
    event_room = event.getRoom() and event.getRoom().getName()
    return [(c,
             bool(c.getLocation() and c.getLocation().getName() == 'CERN' and
                  c.getRoom() and c.getRoom().getName() in av_capable_rooms),
             c.getRoom().getName() if c.getRoom() and c.getRoom().getName() != event_room else None)
            for c in contribs]


def contribution_id(contrib_or_subcontrib):
    """Returns an ID for the contribution/subcontribution"""
    if isinstance(contrib_or_subcontrib, SubContribution):
        return '{}-{}'.format(contrib_or_subcontrib.getContribution().id, contrib_or_subcontrib.id)
    else:
        return unicode(contrib_or_subcontrib.id)


def contribution_by_id(event, contrib_or_subcontrib_id):
    """Returns a contribution/subcontriution from an :func:`contribution_id`-style ID"""
    contrib_id, _, subcontrib_id = contrib_or_subcontrib_id.partition('-')
    contrib = event.getContributionById(contrib_id)
    if contrib and subcontrib_id:
        contrib = contrib.getSubContributionById(subcontrib_id)
    return contrib


def get_selected_contributions(req):
    """Gets the selected contributions for a request.

    :return: list of ``(contribution, capable, custom_room)`` tuples
    """
    if req.event.getType() == 'simple_event':
        return []
    contributions = get_contributions(req.event)
    if req.data.get('all_contributions', True):
        # "all contributions" includes only those in capable rooms
        contributions = [x for x in contributions if x[1]]
    else:
        selected = set(req.data['contributions'])
        contributions = [x for x in contributions if contribution_id(x[0]) in selected]
    return contributions


def get_selected_services(req):
    """Gets the selected services

    :return: list of service names
    """
    return [SERVICES.get(s, s) for s in req.data['services']]


def count_capable_contributions(event):
    """Gets the total and capable-room contribution counts.

    Lectures don't have any contributions, but for the sake of simplifying
    code using this function, they are considered having one or zero capable
    contributions.

    :return: ``(capable, total)`` tuple containing the contribution counts
    """
    if event.getType() == 'simple_event':
        av_capable_rooms = {r.name for r in get_av_capable_rooms()}
        if event.getRoom() and event.getRoom().getName() in av_capable_rooms:
            return 1, 1
        else:
            return 0, 1
    else:
        contribs = get_contributions(event)
        return sum(capable for _, capable, _ in contribs), len(contribs)


def event_has_empty_sessions(event):
    """Checks if the event has any sessions with no contributions"""
    return not all(ss.getContributionList() for ss in event.getSessionSlotList())


def all_agreements_signed(event):
    """Checks if all agreements have been signed"""
    from indico_audiovisual.definition import SpeakerReleaseAgreement
    return SpeakerReleaseAgreement.get_stats_for_signed_agreements(event)[0]


def _get_location_tuple(obj):
    location = obj.getLocation().getName() if obj.getLocation() else None
    room = obj.getRoom().getName() if obj.getRoom() else None
    return location, room


def _get_date_tuple(obj):
    if not hasattr(obj, 'getStartDate') or not hasattr(obj, 'getEndDate'):
        # subcontributions don't have dates
        return None
    return obj.getStartDate().isoformat(), obj.getEndDate().isoformat()


def get_data_identifiers(req):
    """Returns identifiers to determine if relevant data changed.

    Only the event and selected contributions are taken into account.
    While the event date/location doesn't really matter since we already
    check all the contribution dates/locations, we still keep it since a
    location change of the main event could still be relevant to the AV team.

    :return: a dict containing `dates` and `locations`
    """
    event = req.event
    location_identifiers = {}
    date_identifiers = {}
    for obj in [event] + [x[0] for x in get_selected_contributions(req)]:
        obj_id = type(obj).__name__, obj.id
        date_identifiers[obj_id] = _get_date_tuple(obj)
        location_identifiers[obj_id] = _get_location_tuple(obj)
    # we do a json cycle here so we have something that can be compared with data
    # coming from a json storage later. for example, we need lists instead of tuples
    return json.loads(json.dumps({
        'dates': sorted(date_identifiers.items()),
        'locations': sorted(location_identifiers.items())
    }))


def compare_data_identifiers(a, b):
    """Checks if all the identifiers match, besides those that are not in both lists"""
    a = {tuple(key): value for key, value in a}
    b = {tuple(key): value for key, value in b}
    matching_keys = a.viewkeys() & b.viewkeys()
    a = {k: v for k, v in a.iteritems() if k in matching_keys}
    b = {k: v for k, v in b.iteritems() if k in matching_keys}
    return a == b


@celery.task
def send_webcast_ping():
    """Sends a ping notification when a webcast request changes"""
    from indico_audiovisual.plugin import AVRequestsPlugin
    url = AVRequestsPlugin.settings.get('webcast_ping_url')
    if not url:
        return
    AVRequestsPlugin.logger.info('Sending webcast ping to {}'.format(url))
    return requests.get(url).status_code


@celery.task
def send_agreement_ping(agreement):
    """Sends a ping notification when a speaker release is updated"""
    from indico_audiovisual.plugin import AVRequestsPlugin
    url = AVRequestsPlugin.settings.get('agreement_ping_url')
    if not url:
        return
    AVRequestsPlugin.logger.info('Sending agreement ping to {}'.format(url))
    payload = {
        'event_id': agreement.event_id,
        'accepted': None if agreement.pending else agreement.accepted,
        'speaker': {
            'id': agreement.data['speaker_id'],
            'name': agreement.person_name,
            'email': agreement.person_email
        }
    }
    if agreement.data['type'] == 'contribution':
        contrib_id, _, subcontrib_id = agreement.data['contribution'].partition('-')
        payload['contribution_id'] = int(contrib_id)
        if subcontrib_id:
            payload['subcontribution_id'] = int(subcontrib_id)
    return requests.post(url, data={'data': json.dumps(payload)}).status_code


def find_requests(talks=False, from_dt=None, to_dt=None, services=None, states=None):
    """Finds requests matching certain criteria.

    :param talks: if True, yield ``(request, contrib, start_dt)`` tuples
                  instead of just requests, i.e. the same request may be
                  yielded multiple times
    :param from_dt: earliest event/contribution to include
    :param to_dt: latest event/contribution to include
    :param states: acceptable request states (by default anything but withdrawn)
    :param services: set of services that must have been requested
    """
    from indico_audiovisual.definition import AVRequest
    query = Request.find(Request.type == AVRequest.name)
    if states is not None:
        query = query.filter(Request.state.in_(states))
    else:
        query = query.filter(Request.state != RequestState.withdrawn)

    if from_dt is not None or to_dt is not None:
        query = query.join(IndexedEvent, IndexedEvent.id == Request.event_id)

    if from_dt is not None and to_dt is not None:
        # any event that takes place during the specified range
        query = query.filter(db_dates_overlap(IndexedEvent, 'start_date', from_dt, 'end_date', to_dt, inclusive=True))
    elif from_dt is not None:
        # any event that starts on/after the specified date
        query = query.filter(IndexedEvent.start_date >= from_dt)
    elif to_dt is not None:
        # and event that ends on/before the specifed date
        query = query.filter(IndexedEvent.end_date <= to_dt)

    # We only want the latest one for each event
    query = limit_groups(query, Request, Request.event_id, Request.created_dt.desc(), 1)
    for req in query:
        event = req.event
        # Skip requests which do not have the requested services or are outside the date range
        if services and not (set(req.data['services']) & services):
            continue
        elif to_dt is not None and event.getStartDate() > to_dt:
            continue
        if not talks:
            yield req
            continue

        # Lectures don't have contributions so we use the event info directly
        if event.getType() == 'simple_event':
            yield req, event, _get_start_date(event)
            continue

        contribs = [x[0] for x in get_selected_contributions(req)]
        for contrib in contribs:
            contrib_start = _get_start_date(contrib)
            contrib_end = _get_end_date(contrib)
            if from_dt is not None and to_dt is not None and not overlaps((contrib_start, contrib_end),
                                                                          (from_dt, to_dt)):
                continue
            elif from_dt and _get_start_date(contrib) < from_dt:
                continue
            elif to_dt and _get_end_date(contrib) > to_dt:
                continue
            yield req, contrib, _get_start_date(contrib)


def _get_start_date(obj):
    if isinstance(obj, SubContribution):
        return obj.getContribution().getStartDate()
    else:
        return obj.getStartDate()


def _get_end_date(obj):
    if isinstance(obj, SubContribution):
        return obj.getContribution().getEndDate()
    else:
        return obj.getEndDate()
