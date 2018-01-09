# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import json

import requests
from sqlalchemy.orm import joinedload, noload, subqueryload, undefer

from indico.core.celery import celery
from indico.core.db import db
from indico.core.db.sqlalchemy.util.queries import limit_groups
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.util.caching import memoize_request
from indico.util.date_time import overlaps

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


def _get_contrib(contrib_or_subcontrib):
    return (contrib_or_subcontrib.contribution
            if isinstance(contrib_or_subcontrib, SubContribution)
            else contrib_or_subcontrib)


def _contrib_key(contrib):
    # key function to sort contributions and their subcontributions properly
    is_subcontrib = isinstance(contrib, SubContribution)
    return (_get_contrib(contrib).start_dt,
            _get_contrib(contrib),
            is_subcontrib,
            (contrib.position if is_subcontrib else None),
            contrib.title)


@memoize_request
def get_contributions(event):
    """Returns a list of contributions in rooms with AV equipment

    :return: a list of ``(contribution, capable, custom_room)`` tuples
    """
    contribs = (Contribution.query
                .with_parent(event)
                .filter(Contribution.is_scheduled)
                .filter((Contribution.session == None) | Contribution.session.has(is_poster=False))  # noqa
                .options(joinedload('timetable_entry').load_only('start_dt'),
                         joinedload('session_block'),
                         subqueryload('person_links'),
                         undefer('is_scheduled'))
                .all())
    subcontribs = (SubContribution
                   .find(SubContribution.contribution_id.in_(c.id for c in contribs),
                         ~SubContribution.is_deleted)
                   .options(subqueryload('person_links'))
                   .all())
    all_contribs = sorted(contribs + subcontribs, key=_contrib_key)
    av_capable_rooms = get_av_capable_rooms()
    event_room = event.room
    return [(c,
             _get_contrib(c).room in av_capable_rooms,
             _get_contrib(c).room_name if _get_contrib(c).room and _get_contrib(c).room != event_room else None)
            for c in all_contribs]


def contribution_id(contrib_or_subcontrib):
    """Returns an ID for the contribution/subcontribution"""
    prefix = 'sc' if isinstance(contrib_or_subcontrib, SubContribution) else 'c'
    return '{}:{}'.format(prefix, contrib_or_subcontrib.id)


def contribution_by_id(event, contrib_or_subcontrib_id):
    """Returns a contribution/subcontriution from an :func:`contribution_id`-style ID"""
    type_, id_ = contrib_or_subcontrib_id.split(':', 1)
    id_ = int(id_)
    if type_ == 'c':
        return Contribution.query.with_parent(event).filter_by(id=id_).first()
    elif type_ == 'sc':
        return SubContribution.find(SubContribution.id == id_, ~SubContribution.is_deleted,
                                    SubContribution.contribution.has(event=event, is_deleted=False)).first()
    else:
        raise ValueError('Invalid id type: ' + type_)


def get_selected_contributions(req):
    """Gets the selected contributions for a request.

    :return: list of ``(contribution, capable, custom_room)`` tuples
    """
    if req.event.type == 'lecture':
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
    if event.type == 'lecture':
        if event.room in get_av_capable_rooms():
            return 1, 1
        else:
            return 0, 1
    else:
        contribs = get_contributions(event)
        return sum(capable for _, capable, _ in contribs), len(contribs)


def event_has_empty_sessions(event):
    """Checks if the event has any sessions with no contributions"""
    return (SessionBlock.query
            .filter(SessionBlock.session.has(event=event),
                    ~SessionBlock.contributions.any())
            .has_rows())


def all_agreements_signed(event):
    """Checks if all agreements have been signed"""
    from indico_audiovisual.definition import SpeakerReleaseAgreement
    return SpeakerReleaseAgreement.get_stats_for_signed_agreements(event)[0]


def _get_location_tuple(obj):
    obj = _get_contrib(obj)
    return (obj.venue_name or None), (obj.room_name or None)


def _get_date_tuple(obj):
    if isinstance(obj, SubContribution):
        # subcontributions don't have dates
        return None
    return obj.start_dt.isoformat(), obj.end_dt.isoformat()


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
    AVRequestsPlugin.logger.info('Sending webcast ping to %s', url)
    return requests.get(url).status_code


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
    query = Request.query.filter_by(type=AVRequest.name)
    if states is not None:
        query = query.filter(Request.state.in_(states))
    else:
        query = query.filter(Request.state != RequestState.withdrawn)

    if from_dt is not None or to_dt is not None:
        query = query.join(Event).filter(Event.happens_between(from_dt, to_dt))

    # We only want the latest one for each event
    query = limit_groups(query, Request, Request.event_id, Request.created_dt.desc(), 1)
    query = query.options(joinedload('event'))
    for req in query:
        event = req.event
        # Skip requests which do not have the requested services or are outside the date range
        if services and not (set(req.data['services']) & services):
            continue
        elif to_dt is not None and event.start_dt > to_dt:
            continue
        if not talks:
            yield req
            continue

        # Lectures don't have contributions so we use the event info directly
        if event.type == 'lecture':
            yield req, event, event.start_dt
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
    return _get_contrib(obj).start_dt


def _get_end_date(obj):
    return _get_contrib(obj).end_dt
