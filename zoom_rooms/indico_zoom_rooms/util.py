# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import itertools
import typing as t

from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.models.events import Event
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.rb.models.room_attributes import RoomAttribute
from indico.modules.rb.models.rooms import Room
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation


def get_zoom_room_id(obj: Event | Contribution | SessionBlock | Room) -> str | None:
    """Get the Zoom Room Exchange user id for an object (e.g. event) or room.

    Returns `None` if there isn't one.
    """
    room = obj if isinstance(obj, Room) else obj.room

    if (
        room
        and (attributes := room.attributes)
        and (
            user_id_attr := attributes.filter(RoomAttribute.name == 'zoom-rooms-calendar-id')
            .join(RoomAttribute)
            .first()
        )
    ):
        return user_id_attr.value
    else:
        return None


def make_zoom_room_entry_id(user_id: str, obj: Event | Contribution | SessionBlock, vc_room: VCRoom) -> str:
    event_id = obj.id if isinstance(obj, Event) else obj.event.id
    sub_id = ''
    if isinstance(obj, Contribution):
        sub_id = f':contribution:{obj.id}'
    elif isinstance(obj, SessionBlock):
        sub_id = f':block:{obj.id}'

    zoom_id = vc_room.data['zoom_id']

    return f'zoom_meeting:{user_id}@indico:event:{event_id}{sub_id}#{zoom_id}'


def get_vc_room_associations(obj: Session | SessionBlock | Contribution | Event) -> t.Iterable[VCRoomEventAssociation]:
    """
    Get all VC Room Associations tied to the object plus those tied to nested objects inheriting the location from it.

    :param obj: the object in question (`Session`, `SessionBlock`, `Contribution`, `Event`)
    """
    _flatten = lambda it: (assoc for assocs in it for assoc in assocs)

    # drill down into the object's dependencies to figure out which associations are affected by the change
    if isinstance(obj, Contribution):
        return obj.vc_room_associations
    elif isinstance(obj, SessionBlock):
        return itertools.chain(
            obj.vc_room_associations,
            _flatten(contrib.vc_room_associations for contrib in obj.contributions if contrib.inherit_location),
        )
    elif isinstance(obj, Session):
        return itertools.chain(
            _flatten(block.vc_room_associations for block in obj.blocks if block.inherit_location),
            _flatten(
                contrib.vc_room_associations
                for block in obj.blocks
                if block.inherit_location
                for contrib in block.contributions
                if contrib.inherit_location
            ),
        )
    elif isinstance(obj, Event):
        return itertools.chain(
            obj.vc_room_associations,
            _flatten(contrib.vc_room_associations for contrib in obj.contributions if contrib.inherit_location),
            _flatten(
                block.vc_room_associations
                for session in obj.sessions
                if session.inherit_location
                for block in session.blocks
                if block.inherit_location
            ),
        )
    else:
        raise TypeError('Unsupported object')
