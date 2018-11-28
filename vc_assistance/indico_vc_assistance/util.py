# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from sqlalchemy.orm import joinedload

from indico.core.db.sqlalchemy.util.queries import limit_groups
from indico.modules.events import Event
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.rb_new.operations.rooms import search_for_rooms
from indico.modules.vc import VCRoomEventAssociation
from indico.util.caching import memoize_request


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


def has_room_with_vc_attached(event):
    """
    Check if an event or any of its contributions and sessions have some
    vc room attached to a physical room which has videoconference equipment.
    """
    return any(vc for vc in VCRoomEventAssociation.find_for_event(event, include_hidden=True)
               if vc.link_object.room is not None and vc.link_object.room in get_vc_capable_rooms())


def find_requests(from_dt=None, to_dt=None):
    """Finds requests matching certain criteria.

    :param from_dt: earliest event/contribution to include
    :param to_dt: latest event/contribution to include
    """
    from definition import VCAssistanceRequest
    query = Request.query.filter(Request.type == VCAssistanceRequest.name,
                                 Request.state != RequestState.withdrawn)

    if from_dt is not None or to_dt is not None:
        query = query.join(Event).filter(Event.happens_between(from_dt, to_dt))

    # We only want the latest one for each event
    query = limit_groups(query, Request, Request.event_id, Request.created_dt.desc(), 1)
    query = query.options(joinedload('event'))
    for req in query:
        event = req.event
        if to_dt is not None and event.start_dt > to_dt:
            continue
        yield req


@memoize_request
def get_vc_capable_rooms():
    """Returns a list of rooms with VC equipment"""
    from indico_vc_assistance.plugin import VCAssistanceRequestPlugin
    feature = VCAssistanceRequestPlugin.settings.get('room_feature')
    if not feature:
        return set()
    return set(search_for_rooms({'features': [feature.name]}))
