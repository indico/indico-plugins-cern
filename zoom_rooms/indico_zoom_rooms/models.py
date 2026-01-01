# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import typing as t

from sqlalchemy.dialects.postgresql import JSONB

from indico.core.db.sqlalchemy import PyIntEnum, db
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.models.events import Event
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation
from indico.util.enum import IndicoIntEnum
from indico.util.string import format_repr

from indico_zoom_rooms.util import make_zoom_room_entry_id


class EntryData(t.TypedDict):
    start_dt: int
    end_dt: int
    title: str
    url: str


class OperationArgs(t.TypedDict):
    start_dt: t.NotRequired[int]
    end_dt: t.NotRequired[int]
    new_zr_id: t.NotRequired[str]
    title: t.NotRequired[str]


class ExtraArgs(t.TypedDict):
    new_zr_id: t.NotRequired[str]


class ZoomRoomsAction(IndicoIntEnum):
    create = 0
    update = 1
    move = 2
    delete = 3


def get_entry_data(obj: Event | Contribution | SessionBlock, vc_room: VCRoom) -> EntryData:
    entry = obj if isinstance(obj, Event) else obj.timetable_entry
    return {
        'start_dt': int(entry.start_dt.timestamp()),
        'end_dt': int(entry.end_dt.timestamp()),
        'title': vc_room.name,
        'url': vc_room.data['url'],
    }


class ZoomRoomsQueueEntry(db.Model):
    """Pending calendar updates"""

    __tablename__ = 'queue'
    __table_args__ = (
        db.CheckConstraint(
            f'action != {ZoomRoomsAction.delete} OR (entry_data IS NULL AND extra_args IS NULL)', 'delete_has_no_data'
        ),
        db.CheckConstraint(f'action = {ZoomRoomsAction.delete} OR entry_data IS NOT NULL', 'other_actions_have_data'),
        db.CheckConstraint(f'(action = {ZoomRoomsAction.move}) = (extra_args IS NOT NULL)', 'only_move_has_extra_args'),
        {'schema': 'plugin_zoom_rooms'},
    )
    #: Entry ID (mainly used to sort by insertion order)
    id = db.Column(db.Integer, primary_key=True)
    #: ID of the Entry (to be used on the server side)
    entry_id = db.Column(db.String, nullable=False)
    #: ID of the Zoom Room
    zoom_room_id = db.Column(db.String, nullable=False)
    #: :class:`ZoomRoomsAction` to perform
    action = db.Column(PyIntEnum(ZoomRoomsAction), nullable=False)
    #: The actual entry's data
    entry_data: EntryData = db.Column(
        JSONB(none_as_null=True),
    )
    #: Additional args to be sent with the request
    extra_args: ExtraArgs = db.Column(
        JSONB(none_as_null=True),
    )

    def __repr__(self):
        return format_repr(self, 'id', 'entry_id', action=None)

    @classmethod
    def record(
        cls,
        action: int,
        zoom_room_id: str,
        assoc: VCRoomEventAssociation | None = None,
        obj: Event | Contribution | SessionBlock | None = None,
        vc_room: VCRoom | None = None,
        args: OperationArgs | None = None,
    ):
        """Record in the database a ZoomRoomsQueueEntry based on an action and its parameters."""
        if obj is None and assoc is not None:
            obj = assoc.link_object
            vc_room = vc_room or assoc.vc_room
        elif assoc is None and (obj is None or vc_room is None):
            raise ValueError('Either assoc or obj + vc_room must be provided')

        args = args or {}

        if new_zr_id := args.pop('new_zr_id', None):
            extra_args = {'new_zr_id': new_zr_id}
        else:
            extra_args = None

        entry_data = None if action == ZoomRoomsAction.delete else EntryData(get_entry_data(obj, vc_room), **args)
        entry = cls(
            action=action,
            entry_id=make_zoom_room_entry_id(zoom_room_id, obj, vc_room),
            # DELETE operations have no additional parameters, only the ID
            entry_data=entry_data,
            extra_args=extra_args,
            zoom_room_id=zoom_room_id,
        )
        db.session.add(entry)
        db.session.flush()
