# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import time

from sqlalchemy.orm import joinedload, subqueryload, undefer

from indico.core.db import db
from indico.core.db.sqlalchemy.util.queries import limit_groups
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.models.events import EventType
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.sessions import Session
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.room_features import RoomFeature
from indico.modules.rb.models.rooms import Room
from indico.modules.vc import VCRoomEventAssociation
from indico.util.caching import memoize_request


WORKING_TIME_PERIOD = (time(8, 30), time(17, 30))


def can_request_assistance(user):
    """Check if a user can request VC assistance"""
    return _is_in_acl(user, 'authorized')


def is_vc_support(user):
    """Check if a user is VC support"""
    return _is_in_acl(user, 'vc_support')


def _is_in_acl(user, acl):
    from indico_vc_assistance.plugin import VCAssistanceRequestPlugin
    if user.is_admin:
        return True
    return VCAssistanceRequestPlugin.settings.acls.contains_user(acl, user)


def has_vc_rooms(event):
    """
    Check whether the event or any of its contributions and sessions has some
    vc room created.
    """
    return any(VCRoomEventAssociation.find_for_event(event, include_hidden=True))


def has_vc_capable_rooms(event):
    """
    Check whether the event or any of its contributions and sessions has some
    vc capable room attached.
    """
    capable_rooms = get_vc_capable_rooms()
    return (event.room in capable_rooms
            or any(c.room for c in event.contributions if c.room in capable_rooms)
            or any([(s.room, sb.room) for s in event.sessions for sb in s.blocks
                    if sb.room in capable_rooms or s.room in capable_rooms]))


def has_vc_rooms_attached_to_capable(event):
    """Check whether the event or any of its contributions and sessions has some
    vc room created and those are linked to a vc capable room.
    """
    return any(vc for vc in VCRoomEventAssociation.find_for_event(event, include_hidden=True)
               if vc.link_object.room is not None and vc.link_object.room in get_vc_capable_rooms())


def find_requests(from_dt=None, to_dt=None, contribs_and_sessions=True):
    """Finds requests matching certain criteria.

    :param from_dt: earliest event/contribution to include
    :param to_dt: latest event/contribution to include
    :param contribs_and_sessions: whether it should return contributions and sessions or only request
    """
    from .definition import VCAssistanceRequest
    query = Request.query.join(Event).filter(~Event.is_deleted,
                                             Request.type == VCAssistanceRequest.name,
                                             Request.state == RequestState.accepted)

    if from_dt is not None or to_dt is not None:
        query = query.filter(Event.happens_between(from_dt, to_dt))

    # We only want the latest one for each event
    query = limit_groups(query, Request, Request.event_id, Request.created_dt.desc(), 1)
    query = query.options(joinedload('event'))
    for req in query:
        event = req.event
        if to_dt is not None and event.start_dt > to_dt:
            continue
        if not contribs_and_sessions:
            yield req
        else:
            contribs = [x[0] for x in get_capable(req, get_contributions)]
            session_blocks = [x[0] for x in get_capable(req, get_session_blocks)]
            yield req, contribs, session_blocks


@memoize_request
def get_vc_capable_rooms():
    """Returns a list of rooms with VC equipment"""
    from indico_vc_assistance.plugin import VCAssistanceRequestPlugin
    feature = VCAssistanceRequestPlugin.settings.get('room_feature')
    if not feature:
        return set()
    feature_criterion = Room.available_equipment.any(EquipmentType.features.any(RoomFeature.name == feature.name))
    return set(Room.query.filter(~Room.is_deleted, feature_criterion))


def _contrib_key(contrib):
    return (contrib.start_dt,
            contrib.title,
            contrib.friendly_id)


@memoize_request
def get_contributions(event):
    """Returns a list of contributions in rooms with VC equipment

    :return: a list of ``(contribution, capable, custom_room)`` tuples
    """
    contribs = (Contribution.query
                .with_parent(event)
                .filter(Contribution.is_scheduled)
                .filter(db.or_(Contribution.session == None,  # noqa
                               Contribution.session.has(db.or_(Session.type == None,  # noqa
                                                               Session.type.has(is_poster=False)))))
                .options(joinedload('timetable_entry').load_only('start_dt'),
                         joinedload('session_block'),
                         subqueryload('person_links'),
                         undefer('is_scheduled'))
                .all())
    all_contribs = sorted(contribs, key=_contrib_key)
    vc_capable_rooms = get_vc_capable_rooms()
    event_room = event.room
    return [(c,
             c.room in vc_capable_rooms,
             c.room_name if c.room and c.room != event_room else None)
            for c in all_contribs]


@memoize_request
def get_session_blocks(event):
    """Returns a list of contributions in rooms with VC equipment

    :return: a list of ``(contribution, capable, custom_room)`` tuples
    """
    session_blocks = (SessionBlock.query
                      .filter(SessionBlock.session.has(event=event, is_deleted=False)))
    vc_capable_rooms = get_vc_capable_rooms()
    event_room = event.room
    return [(sb,
             sb.room in vc_capable_rooms,
             sb.room_name if sb.room and sb.room != event_room else None)
            for sb in session_blocks]


def get_capable(req, get_contribs_or_session_blocks):
    """Gets the capable contributions/session blocks with associated vc room for a request.

    :return: list of ``contribution`` or ``session block``
    """
    if req.event.type_ == EventType.lecture:
        return []
    return [x for x in get_contribs_or_session_blocks(req.event) if x[1] and x[0].vc_room_associations]


def start_time_within_working_hours(event):
    return WORKING_TIME_PERIOD[0] <= event.start_dt_local.time() <= WORKING_TIME_PERIOD[1]
