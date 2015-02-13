from flask import session, request

from MaKaC.webinterface.rh.conferenceModif import RHConferenceModifBase

from indico_ravem.actions import get_room_status, connect_room, disconnect_room

# __all__ = ('RHRavemRoomStatus', 'RHRavemConnectRoom', 'RHRavemDisconnectRoom')


class RHRavemRoomStatus(RHConferenceModifBase):
    def _process(self):
        return get_room_status(room_name)


class RHRavemConnectRoom(RHConferenceModifBase):
    def _process(self):
        return connect_room(room_name, booking)


class RHRavemDisconnectRoom(RHConferenceModifBase):
    def _process(self):
        return disconnect_room(room_name, booking)
