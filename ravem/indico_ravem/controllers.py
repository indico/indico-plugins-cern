from flask import request, jsonify
from werkzeug.exceptions import NotFound

from indico.modules.vc.models.vc_rooms import VCRoomEventAssociation
from indico.util.i18n import _
from MaKaC.webinterface.rh.conferenceModif import RHConferenceModifBase

from indico_ravem.operations import get_room_status, connect_room, disconnect_room
from indico_ravem.util import RavemOperationException, RavemException

__all__ = ('RHRavemRoomStatus', 'RHRavemConnectRoom', 'RHRavemDisconnectRoom')


class RHRavemBase(RHConferenceModifBase):
    def _checkParams(self, params):
        RHConferenceModifBase._checkParams(self, params)
        id_ = request.view_args['event_vc_room_id']
        self.event_vc_room = VCRoomEventAssociation.find_one(id=id_)
        if not self.event_vc_room:
            raise NotFound(_("Event VC Room not found for id {id}").format(id=id_))
        if self.event_vc_room.link_object.getConference().id != self._conf.id:
            raise NotFound(_("Event VC Room id {id} does not match conference id {conf_id}")
                           .format(id=id_, conf_id=self._conf.id))
        room = self.event_vc_room.link_object.getRoom() if self.event_vc_room.link_object else None
        if not room:
            raise NotFound(_("Event VC Room ({id}) is not linked to an event with a compatible room").format(id=id_))
        self.room_name = room.getName()


class RHRavemRoomStatus(RHRavemBase):
    def _process(self):
        try:
            response = get_room_status(self.room_name)
            response['success'] = True
        except RavemOperationException as err:
            response = {'success': False, 'reason': err.reason, 'message': err.message}
        except RavemException as err:
            response = {'success': False, 'reason': 'operation-failed', 'message': err.message}

        return jsonify(response)


class RHRavemConnectRoom(RHRavemBase):
    def _process(self):
        force = request.args.get('force') == '1'
        try:
            connect_room(self.room_name, self.event_vc_room.vc_room, force=force)
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
            disconnect_room(self.room_name, self.event_vc_room.vc_room, force=force)
        except RavemOperationException as err:
            response = {'success': False, 'reason': err.reason, 'message': err.message}
        except RavemException as err:
            response = {'success': False, 'reason': 'operation-failed', 'message': err.message}
        else:
            response = {'success': True}

        return jsonify(response)
