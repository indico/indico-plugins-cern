# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import typing as t
from functools import wraps

from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField, FloatField, URLField
from wtforms.validators import URL, DataRequired, NumberRange

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.models.events import Event
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.events.sessions.models.sessions import Session
from indico.modules.events.timetable.models.entries import TimetableEntry
from indico.modules.vc.models.vc_rooms import VCRoom, VCRoomEventAssociation
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico.web.forms.widgets import SwitchWidget

from indico_zoom_rooms import _
from indico_zoom_rooms.models import OperationArgs, ZoomRoomsAction, ZoomRoomsQueueEntry
from indico_zoom_rooms.util import get_vc_room_associations, get_zoom_room_id


class PluginSettingsForm(IndicoForm):
    debug = BooleanField(
        _('Debug mode'),
        widget=SwitchWidget(),
        description=_('If enabled, requests are not sent to the API but logged instead'),
    )
    service_url = URLField(
        _('Service URL'), [URL(require_tld=False)], description=_('The URL of the CERN calendar service')
    )
    docs_url = URLField(_('Documentation URL'), [URL()], description=_('The URL the "Zoom Rooms" buttons will link to'))
    token = IndicoPasswordField(
        _('Token'),
        [DataRequired()],
        toggle=True,
        description=_('The token used to authenticate with the CERN calendar service'),
    )
    timeout = FloatField(_('Request timeout'), [NumberRange(min=0.25)], description=_('Request timeout in seconds'))


def only_zoom_rooms(f):
    """Limit the wrapped handler to only objects which are somehow tied to a VCRoom and a Room with
       ZoomRooms enabled."""

    @wraps(f)
    def _wrapper(obj: Event | Contribution | SessionBlock | VCRoomEventAssociation, *args: tuple, **kwargs: dict):
        link_obj = obj.link_object if isinstance(obj, VCRoomEventAssociation) else obj

        if not link_obj.room:
            return

        # do not bother doing anything if the room is not ZR-enabled
        if get_zoom_room_id(link_obj.room):
            f(obj, *args, **kwargs)

    return _wrapper


@only_zoom_rooms
def _delete_zoom_association(old_link: SessionBlock | Contribution | Event, vc_room: VCRoom):
    """Handle deleted VC room associations (given the corresponding object)."""
    if zr_id := get_zoom_room_id(old_link.room):
        ZoomRoomsQueueEntry.record(ZoomRoomsAction.delete, zr_id, obj=old_link, vc_room=vc_room)


@only_zoom_rooms
def _handle_link_object_created(assoc: VCRoomEventAssociation):
    """Handle the creation of a new object (given the corresponding association)."""
    if assoc.vc_room.type == 'zoom':
        if zr_id := get_zoom_room_id(assoc.link_object.room):
            ZoomRoomsQueueEntry.record(ZoomRoomsAction.create, zr_id, assoc=assoc)


@only_zoom_rooms
def _handle_link_object_dt_change(
    obj: SessionBlock | Contribution | Event,
    changes: dict[str, t.Any],
):
    """Handle the changes of date/time of an object."""
    if zr_id := get_zoom_room_id(obj.room):
        # do not handle sub-objects, as the corresponding signals are called directly
        for assoc in obj.vc_room_associations:
            if assoc.vc_room.type == 'zoom':
                args = OperationArgs()
                if 'start_dt' in changes:
                    args['start_dt'] = int(changes['start_dt'][1].timestamp())
                if 'end_dt' in changes:
                    args['end_dt'] = int(changes['end_dt'][1].timestamp())

                ZoomRoomsQueueEntry.record(ZoomRoomsAction.update, zr_id, assoc=assoc, args=args)


def _handle_contribution_move(obj: Contribution, original_block: SessionBlock, new_block: SessionBlock):
    """Handle contributions moved between blocks."""
    # block is None -> attached to the event
    if (orig_zr_id := get_zoom_room_id(original_block.room if original_block else obj.event.room)) != (
        new_zr_id := get_zoom_room_id(new_block.room if new_block else obj.event.room)
    ):
        _handle_linked_obj_location_change(obj, orig_zr_id, new_zr_id)


def _handle_linked_obj_location_change(
    obj: SessionBlock | Contribution | Event,
    old_zr_id: str | None,
    new_zr_id: str | None,
):
    """Handle changes of location in an object (given the old/new ZoomRoom ID)."""
    match old_zr_id, new_zr_id:
        case None, None:
            # this doesn't concern us as there are no zoom rooms involved
            return
        case None, zr_id:
            make_op = lambda assoc: ZoomRoomsQueueEntry.record(ZoomRoomsAction.create, t.cast(str, zr_id), assoc=assoc)
        case zr_id, None:
            make_op = lambda assoc: ZoomRoomsQueueEntry.record(ZoomRoomsAction.delete, t.cast(str, zr_id), assoc=assoc)
        case old_zr_id, new_zr_id:
            make_op = lambda assoc: ZoomRoomsQueueEntry.record(
                ZoomRoomsAction.move, t.cast(str, old_zr_id), assoc=assoc, args={'new_zr_id': t.cast(str, new_zr_id)}
            )

    # go over all associations, incl. nested ones
    for assoc in get_vc_room_associations(obj):
        if assoc.vc_room.type == 'zoom':
            make_op(assoc)


def _check_link_object_for_updates(
    obj: Session | SessionBlock | Contribution | Event,
    changes: dict[str, t.Any] | None = None,
):
    """Check "newsworthy" updates in an object, given a set of changes. Call the appropriate handling functions."""
    if changes is None:
        changes = {}

    # contribution move between session blocks / top level, and it is inheriting its location
    if session_block_data := changes.get('session_block'):
        old_block, new_block = session_block_data
        _handle_contribution_move(
            obj,
            old_block,
            new_block,
        )

    # event/contribution/session/block location changed explicitly
    if location_data := changes.get('location_data'):
        old_data, new_data = location_data

        # if the room wasn't updated, nothing to do
        if 'room' in old_data:
            old_room = old_data['room']
            # this won't fail since there is a 'room 'in either dict
            new_room = new_data['room']

            old_zr_id = get_zoom_room_id(old_room) if old_room else None
            new_zr_id = get_zoom_room_id(new_room) if new_room else None

            _handle_linked_obj_location_change(obj, old_zr_id, new_zr_id)

    # start or end date changed
    if set(changes) & {'start_dt', 'end_dt'}:
        _handle_link_object_dt_change(obj, {k: v for k, v in changes.items() if k in ('start_dt, end_dt')})


def _signal_link_object_updated(obj: Session | SessionBlock | Contribution | Event, changes: dict | None = None):
    _check_link_object_for_updates(obj, changes)


def _signal_tt_entry_updated(obj_type, entry: TimetableEntry, obj: Contribution | SessionBlock, changes: dict):
    _check_link_object_for_updates(obj, changes)


def _signal_zoom_meeting_created(vc_room: VCRoom, assoc: VCRoomEventAssociation, event: Event):
    _handle_link_object_created(assoc)


def _signal_zoom_meeting_cloned(
    old_assoc: VCRoomEventAssociation,
    new_assoc: VCRoomEventAssociation,
    vc_room: VCRoom,
    link_object: SessionBlock | Contribution | Event,
):
    # on clone, clone also the zoom room calendar entry
    if new_assoc.link_object.room:
        _handle_link_object_created(new_assoc)


def _signal_zoom_meeting_association_attached(
    assoc: VCRoomEventAssociation,
    vc_room: VCRoom,
    event: Event,
    data: dict,
    old_link: VCRoomEventAssociation | None,
    new_room: bool = False,
):
    # ignore associations to new rooms, since that's already handled by `new_vc_room`
    if not new_room:
        # this is a new association to an existing room, hence a new slot has to be created
        _handle_link_object_created(assoc)


def _signal_zoom_meeting_association_detached(
    assoc: VCRoomEventAssociation,
    vc_room: VCRoom,
    old_link: Event | Contribution | SessionBlock,
    event: Event,
    data: dict | None = None,
):
    if vc_room.type == 'zoom':
        # when a room is detached from an event/contribution/session block, delete the corresponding zoom room entry
        _delete_zoom_association(old_link, vc_room)


def _signal_zoom_meeting_data_updated(vc_room: VCRoom, data: dict):
    if vc_room.type == 'zoom' and (name := data.get('name')) and name != vc_room.name:
        for assoc in vc_room.events:
            if zr_id := get_zoom_room_id(assoc.link_object):
                ZoomRoomsQueueEntry.record(ZoomRoomsAction.update, zr_id, assoc=assoc, args=OperationArgs(title=name))


class ZoomRoomsPlugin(IndicoPlugin):
    """Zoom Rooms

    Zoom Rooms / Exchange synchronization plugin for Indico."""

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {'debug': False, 'service_url': None, 'docs_url': '', 'token': None, 'timeout': 3}

    def init(self):
        super().init()
        # Here we plug the various object signals into the action tracking code
        # Consult the README.md for a summary of the logic behind
        self.connect(signals.event.contribution_updated, _signal_link_object_updated)
        self.connect(signals.event.session_block_updated, _signal_link_object_updated)
        self.connect(signals.event.updated, _signal_link_object_updated)
        self.connect(signals.event.times_changed, _signal_tt_entry_updated, sender=Contribution)
        self.connect(signals.event.times_changed, _signal_tt_entry_updated, sender=SessionBlock)
        self.connect(signals.vc.new_vc_room, _signal_zoom_meeting_created)
        self.connect(signals.vc.cloned_vc_room, _signal_zoom_meeting_cloned)
        self.connect(signals.vc.attached_vc_room, _signal_zoom_meeting_association_attached)
        self.connect(signals.vc.detached_vc_room, _signal_zoom_meeting_association_detached)
        self.connect(signals.vc.updated_vc_room_data, _signal_zoom_meeting_data_updated)

        self.template_hook('manage-event-vc-extra-buttons', self.inject_button)
        self.template_hook('event-vc-extra-buttons', self.inject_button)
        self.template_hook('event-timetable-vc-extra-buttons', self.inject_button)

    def inject_button(self, event_vc_room: VCRoomEventAssociation, **kwargs: dict):
        if event_vc_room.vc_room.type != 'zoom' or not event_vc_room.link_object.room:
            return

        if zr_id := get_zoom_room_id(event_vc_room.link_object):
            return render_plugin_template(
                'explanation.html',
                room_name=event_vc_room.link_object.room.full_name,
                event_vc_room=event_vc_room,
                zr_id=zr_id,
                docs_url=ZoomRoomsPlugin.settings.get('docs_url'),
                **kwargs,
            )
