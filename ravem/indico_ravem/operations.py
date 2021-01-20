# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from time import sleep

from indico_ravem import _
from indico_ravem.api import BaseAPI, ZoomAPI
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


API = {
    'zoom': ZoomAPI(),
}


def get_room_status(room_name, room_verbose_name=None):
    """Get the status of a room given its name.

    :param room_name: str -- The name of the room whose status is fetched
    :param room_verbose_name: str -- The prettier name of a room, used in the
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :returns: dict -- the status of the room with the following information:
        - `room_name`: The room identifier
        - `vc_room_id`: The id of the vc_room the room is connected to or
        `None` if the room is not connected.
        - `service_type`: The type of service, given by RAVEM. Usually '"zoom"'
        or `"other"`
        - `connected`: `True` if the room is connected, `False` otherwise
    """
    _room_name = room_verbose_name or room_name
    response = BaseAPI.get_endpoint_status(room_name)
    if response.get("error"):
        RavemPlugin.logger.error(
            "Failed to get status of room %s with error: %s",
            _room_name,
            response["error"],
        )
        raise RavemException(
            _(
                "Failed to get status of room {room} with error: {response[error]}"
            ).format(room=_room_name, response=response)
        )
    status = next(s for s in response['services'] if s['name'] == 'videoconference')
    return {
        'room_name': response['roomName'],
        'vc_room_id': status['eventName'],
        # As per RAVEM api v2, deviceType is identified per room, instead of per room service
        'service_type': response['deviceType'],
        'connected': status['status']
    }


def connect_room(room_name, vc_room, force=False, room_verbose_name=None):
    """Connects a room given its name with a given vc_room.

    If a `RavemException` is raised it is important to verify the
    `reason` attribute of the exception.
    If the room is already connected to the given VC room, the `reason` will be:
    `"already-connected"`.
    If the room is already connected to another VC room and we are not forcing
    the connection, the `reason` will be: `"connected-other"`.

    Forcing the connection (`force=True`) means disconnecting the room from the
    VC room it is currently connected (if it is connected to a different VC room
    than the given one) This option does not guarantee to establish the
    connection as RAVEM might fail to disconnect the room or connect it
    afterwards to the new VC room.

    This operation will also take time as RAVEM is unable to indicate us if the
    disconnection was successful. It is thus required to poll RAVEM. The amount
    of polls and interval between them is defined in the settings. Note that a
    failure to disconnect might simply be slowness in the network coupled with
    aggressive polling settings which fail to poll the expected status in time.

    :param room_name: str -- The name of the room to connect
    :param vc_room: VCRoom -- The VC room instance to connect with the room.
    :param force: bool -- Whether to force the connection between the room and
        the VC room. Defaults to `False`
    :param room_verbose_name: str -- The prettier name of a room, used in the
        error messages.

    :raises: RavemException
    """
    _room_name = room_verbose_name or room_name
    status = get_room_status(room_name)
    _ensure_room_service(room_name, vc_room.type, status["service_type"])
    service_api = get_api(vc_room.type)
    vc_room_id = service_api.get_room_id(vc_room.data)
    if status['connected']:
        if status['vc_room_id'] == vc_room_id:
            raise RavemException(
                _("The room {room} is already connected to the videoconference room {vc_room}")
                .format(room=_room_name, vc_room=vc_room_id),
                'already-connected'
            )
        if not force:
            raise RavemException(
                _("The room {room} is connected to another videoconference room: {vc_room}")
                .format(room=_room_name, vc_room=status['vc_room_id']),
                'connected-other'
            )
        disconnect_response = service_api.disconnect_endpoint(room_name, vc_room_id)
        if disconnect_response.get('error'):
            RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s with error: %s",
                                     _room_name, status['vc_room_id'], disconnect_response['error'])
            raise RavemException(
                _("Failed to disconnect the room {room} from the videoconference room {vc_room} with error: "
                  "{response[error]}").format(room=_room_name, vc_room=status['vc_room_id'],
                                              response=disconnect_response)
            )

        # A "success" response from RAVEM doesn't mean the room is disconnected.
        # We need to poll RAVEM for the status of the room.

        # ms in settings but time.sleep takes sec
        polling_interval = RavemPlugin.settings.get('polling_interval') / 1000.0
        for attempt in range(RavemPlugin.settings.get('polling_limit')):
            status = get_room_status(room_name)
            if not status['connected']:
                break
            sleep(polling_interval)
        else:
            RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s "
                                     "with an unknown error", _room_name, status['vc_room_id'])
            raise RavemException(_("Failed to disconnect the room {room} from the videoconference room {vc_room} with "
                                   "an unknown error").format(room=_room_name, vc_room=status['vc_room_id']))

    response = service_api.connect_endpoint(room_name, vc_room_id)

    if response.get('error'):
        RavemPlugin.logger.error("Failed to connect the room %s to the videoconference room %s with error: %s",
                                 _room_name, vc_room_id, response['error'])
        raise RavemException(
            _("Failed to connect the room {room} to the videoconference room {vc_room} "
              "with error: {response[error]}").format(room=_room_name, vc_room=vc_room_id, response=response)
        )
    return response.get('success', False)


def disconnect_room(room_name, vc_room, force=False, room_verbose_name=None):
    """Disconnect a room given its name from a given vc_room.

    If a `RavemException` is raised it is important to verify the
    `reason` attribute of the exception.
    If the room is already disconnected, the `reason` will be:
    `"already-disconnected"`.
    If the room is connected to another VC room and we are not forcing
    the disconnection, the `reason` will be: `"connected-other"`.

    Forcing the disconnection (`force=True`) will force the room to disconnect
    from the VC room it is connected to, regardless of the given VC room.

    :param room_name: str -- The name of the room to disconnect
    :param vc_room: VCRoom -- The VC room instance to disconnect from the room.
    :param force: bool -- Whether to force the disconnection of the room.
        Defaults to `False`
    :param room_verbose_name: str -- The prettier name of a room, used in the
        error messages.

    :raises: RavemException
    """
    _room_name = room_verbose_name or room_name
    status = get_room_status(room_name)
    _ensure_room_service(room_name, vc_room.type, status['service_type'])
    service_api = get_api(vc_room.type)
    vc_room_id = service_api.get_room_id(vc_room.data)
    if not status['connected']:
        raise RavemException(
            _("The room {room} is already disconnected.").format(room=_room_name),
            'already-disconnected'
        )
    if status['vc_room_id'] != vc_room_id:
        if not force:
            raise RavemException(
                _("The room {room} is connected to another videoconference room: {vc_room}")
                .format(room=_room_name, vc_room=status['vc_room_id']),
                'connected-other'
            )
        else:
            RavemPlugin.logger.info("Force disconnect of room %s from videoconference %s",
                                    _room_name, status['vc_room_id'])

    response = service_api.disconnect_endpoint(room_name, vc_room_id)

    if response.get('error'):
        if response['error'] == 'Call already disconnected':
            raise RavemException(
                _('The room {room} is already disconnected.').format(room=_room_name),
                'already-disconnected'
            )

        RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s with error: %s",
                                 _room_name, vc_room_id, response['error'])
        raise RavemException(
            _("Failed to disconnect the room {room} from the videoconference room {vc_room} with error: "
              "{response[error]}").format(room=_room_name, vc_room=vc_room_id, response=response)
        )
    return response.get('success', False)


def get_api(service_type):
    try:
        return API[service_type]
    except KeyError:
        raise RavemException(f'The videoconference service {service_type} is not supported')


def _ensure_room_service(room_name, room_service, device_type):
    """Ensure the virtual room conference service matches with what the physical room supports"""
    if room_service and device_type != room_service:
        RavemPlugin.logger.error(
            "%s is not supported in the room %s", room_service, room_name
        )
        raise RavemException(
            _("{service} is not supported in the room {room}").format(
                service=room_service, room=room_name
            )
        )
