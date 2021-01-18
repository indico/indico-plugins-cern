# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod

from indico_ravem.util import ravem_api_call


__all__ = ('BaseAPI', 'ZoomAPI')


class BaseAPI:
    __metaclass__ = ABCMeta

    @staticmethod
    def get_endpoint_status(room_name):
        """Returns the status of an physical room.

        This call returns the status of a room equipped with videoconference capable device

        :param room_name: str -- the name of the physical room
        """
        room_name = room_name.replace('/', '-', 1)
        return ravem_api_call('rooms/details', method='GET',
                              params={'where': 'room_name', 'value': room_name})

    @abstractmethod
    def get_room_id(self, vc_room_data):
        """Returns the provider specific room ID."""
        pass

    @abstractmethod
    def connect_endpoint(self, room_name, vc_room_id):
        """Connects a physical room to a videoconference room using the RAVEM API.

        This call will return "OK" as a result immediately if RAVEM can (or has
        started to) perform the operation. This does not mean the operation has
        actually succeeded. One should poll for the status of the room afterwards
        using the `get_endpoint_status` method after some delay to allow the
        operation to be performed..

        :param room_name: str -- the name of the physical room
        :param vc_room_id: str -- the provider specific id of the
            videoconference room
        """
        pass

    @abstractmethod
    def disconnect_endpoint(self, room_name, vc_room_id):
        """Disconnects a physical room from a videoconference room using the RAVEM API.

        This call will return "OK" as a result immediately if RAVEM can (or has
        started to) perform the operation. This does not mean the operation has
        actually succeeded. One should poll for the status of the room afterwards
        using the `get_endpoint_status` method after some delay to allow the
        operation to be performed.

        :param room_name: str -- the name of the physical room
        :param vc_room_id: str -- the provider specific id of the
            videoconference room
        """
        pass


class ZoomAPI(BaseAPI):
    SERVICE_TYPE = 'zoom'

    def get_room_id(self, vc_room_data):
        return str(vc_room_data["zoom_id"])

    def connect_endpoint(self, room_name, vc_room_id):
        return ravem_api_call('%s/connect' % self.SERVICE_TYPE, method='POST',
                              json={'meetingId': vc_room_id, 'roomName': room_name})

    def disconnect_endpoint(self, room_name, vc_room_id):
        return ravem_api_call('%s/disconnect' % self.SERVICE_TYPE, method='POST', json={'roomName': room_name})
