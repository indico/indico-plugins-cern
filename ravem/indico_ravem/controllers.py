# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import jsonify, request
from werkzeug.exceptions import NotFound

from indico.core.errors import IndicoError
from indico.modules.vc.models.vc_rooms import VCRoomEventAssociation
from indico.web.rh import RH

from indico_ravem import _
from indico_ravem.operations import connect_room, disconnect_room, get_room_status
from indico_ravem.util import RavemException, RavemOperationException, has_access


__all__ = ('RHRavemRoomStatus', 'RHRavemConnectRoom', 'RHRavemDisconnectRoom')


class RHRavemBase(RH):
    def _check_access(self):
        if not has_access(self.event_vc_room):
            raise RavemException(_("Not authorized to access the room with RAVEM"))

    def _process_args(self):
        id_ = request.view_args['event_vc_room_id']
        self.event_vc_room = VCRoomEventAssociation.find_one(id=id_)
        if not self.event_vc_room:
            raise NotFound(_("Event VC Room not found for id {id}").format(id=id_))

        if not self.event_vc_room.link_object:
            raise IndicoError(_("Event VC Room ({id}) is not linked to anything").format(id=id_))

        event_id = int(request.view_args['confId'])
        event = self.event_vc_room.link_object.event
        if not event:
            raise IndicoError(_("Event VC Room ({id}) does not have an event").format(id=id_))

        if event.id != event_id:
            raise IndicoError(_("Event VC Room ({id}) does not have an event with the id {conf.id}")
                              .format(id=id_, conf=event))

        room = self.event_vc_room.link_object.room if self.event_vc_room.link_object else None
        if not room:
            raise IndicoError(_("Event VC Room ({id}) is not linked to an event with a room").format(id=id_))

        self.room_name = room.generate_name()
        self.room_special_name = room.name

        if not self.room_name:
            raise IndicoError(_("Event VC Room ({id}) is not linked to an event with a valid room").format(id=id_))

        if not self.room_special_name:
            self.room_special_name = self.room_name


class RHRavemRoomStatus(RHRavemBase):
    def _process(self):
        try:
            response = get_room_status(self.room_name, room_special_name=self.room_special_name)
            response['success'] = True
        except RavemException as err:
            response = {'success': False, 'reason': 'operation-failed', 'message': err.message}
        return jsonify(response)


class RHRavemConnectRoom(RHRavemBase):
    def _process(self):
        force = request.args.get('force') == '1'
        try:
            connect_room(self.room_name, self.event_vc_room.vc_room, force=force,
                         room_special_name=self.room_special_name)
        except RavemOperationException as err:
            response = {'success': False, 'reason': err.reason, 'message': err.message}
        except RavemException as err:
            response = {'success': False, 'reason': 'operation-failed', 'message': err.message}
        else:
            response = {'success': True}
        return jsonify(response)


class RHRavemDisconnectRoom(RHRavemBase):
    def _process(self):
        force = request.args.get('force') == '1'
        try:
            disconnect_room(self.room_name, self.event_vc_room.vc_room, force=force,
                            room_special_name=self.room_special_name)
        except RavemOperationException as err:
            response = {'success': False, 'reason': err.reason, 'message': err.message}
        except RavemException as err:
            response = {'success': False, 'reason': 'operation-failed', 'message': err.message}
        else:
            response = {'success': True}

        return jsonify(response)
