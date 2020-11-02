# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from time import sleep

from indico_ravem import _
from indico_ravem.api import ZoomAPI, VidyoAPI, BaseAPI
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException, RavemOperationException

_all__ = ('get_room_status', 'connect_room', 'disconnect_room')
API = {
    'zoom': ZoomAPI(),
    'vidyo': VidyoAPI()
}


def get_room_status(room_name, legacy_ip=None):
    """Get the status of a room given its name.

    :param room_name: str -- The name of the room whose status is fetched
    :param legacy_ip: str -- The H323 IP (if any)

    :returns: dict -- the status of the room with the following information:
        - `room_name`: The room identifier
        - `vc_room_id`: The id of the vc_room the room is connected to or
        `None` if the room is not connected.
        - `service_type`: The type of service, given by RAVEM. Usually '"vidyo"'
        or `"other"`
        - `connected`: `True` if the room is connected, `False` otherwise
        - `room_endpoint`: vidyo username or RAVEM prefixed H323 IP
    """
    response = BaseAPI.get_endpoint_status(room_name)
    status = next(s for s in response['services'] if s['name'] == 'videoconference')
    endpoint = response['vidyoUsername']
    if response['legacyHostname']:
        endpoint = '{prefix}{ip}'.format(
            prefix=RavemPlugin.settings.get('prefix'), ip=legacy_ip
        )
    return {
        'room_name': response['roomName'],
        'vc_room_id': status['eventName'],
        'service_type': response['deviceType'],
        'connected': status['status'],
        'room_endpoint': endpoint
    }


def connect_room(room_name, vc_room, force=False, room_verbose_name=None, legacy_ip=None):
    """Connects a room given its name with a given vc_room.

    If a `RavemOperationException` is raised it is important to verify the
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
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :raises: RavemOperationException, RavemException
    """
    room_verbose_name = room_verbose_name or room_name
    status = get_room_status(room_name, legacy_ip)
    service_api = API[vc_room.type]
    vc_room_id = service_api.get_room_id(vc_room)
    if status['connected']:
        if status['vc_room_id'] == vc_room_id:
            raise RavemOperationException(
                _("The room {room} is already connected to the room {vc_room.name}")
                .format(room=room_verbose_name, vc_room=vc_room),
                'already-connected'
            )
        if not force:
            raise RavemOperationException(
                _("The room {room} is connected to another room: {vc_room}")
                .format(room=room_verbose_name, vc_room=vc_room_id),
                'connected-other'
            )
        disconnect_response = service_api.disconnect_endpoint(status)
        if disconnect_response.get('error'):
            RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s with error: %s",
                                     room_verbose_name, vc_room_id, disconnect_response['error'])
            raise RavemException(
                _("Failed to disconnect the room {room} from the videoconference room {vc_room} with error: "
                  "{response[error]}").format(room=room_verbose_name, vc_room=vc_room_id, response=disconnect_response)
            )

        # A "success" response from RAVEM doesn't mean the room is disconnected.
        # We need to poll RAVEM for the status of the room.

        # ms in settings but time.sleep takes sec
        polling_interval = RavemPlugin.settings.get('polling_interval') / 1000.0
        for attempt in xrange(RavemPlugin.settings.get('polling_limit')):
            status = get_room_status(room_name, legacy_ip)
            if not status['connected']:
                break
            sleep(polling_interval)
        else:
            RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s "
                                     "with an unknown error", room_verbose_name, vc_room_id)
            raise RavemException(_("Failed to disconnect the room {room} from the videoconference room {vc_room} with "
                                   "an unknown error").format(room=room_verbose_name, vc_room=vc_room_id))

    response = service_api.connect_endpoint(status, vc_room)

    if response.get('error'):
        RavemPlugin.logger.error("Failed to connect the room %s to the videoconference room %s with error: %s",
                                 room_verbose_name, vc_room.name, response['error'])
        raise RavemException(
            _("Failed to connect the room {room} to the videoconference room {vc_room.name} with error: "
              "{response[error]}").format(room=room_verbose_name, vc_room=vc_room, response=response)
        )


def disconnect_room(room_name, vc_room, force=False, room_verbose_name=None):
    """Disconnect a room given its name from a given vc_room.

    If a `RavemOperationException` is raised it is important to verify the
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
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :raises: RavemOperationException, RavemException
    """
    room_verbose_name = room_verbose_name or room_name
    status = get_room_status(room_name)
    service_api = API[vc_room.type]
    vc_room_id = service_api.get_room_id(vc_room)
    if not status['connected']:
        raise RavemOperationException(
            _("The room {room} is already disconnected.").format(room=room_verbose_name),
            'already-disconnected'
        )
    if status['vc_room_id'] != vc_room_id:
        if not force:
            raise RavemOperationException(
                _("The room {room} is connected to another videoconference room: {vc_room}")
                .format(room=room_verbose_name, vc_room=vc_room_id),
                'connected-other'
            )
        else:
            RavemPlugin.logger.info("Force disconnect of room %s from videoconference %s "
                                    "(expected to disconnect from videoconference %s)",
                                    room_verbose_name, vc_room_id, vc_room.name)

    response = service_api.disconnect_endpoint(status, vc_room)

    if response.get('error'):
        if response['error'] == 'Call already disconnected':
            raise RavemOperationException(
                _("The room {room} is already disconnected.").format(room=room_verbose_name),
                'already-disconnected'
            )

        RavemPlugin.logger.error("Failed to disconnect the room %s from the videoconference room %s with error: %s",
                                 room_verbose_name, vc_room_id, response['error'])
        raise RavemException(
            _("Failed to disconnect the room {room} from the videoconference room {vc_room} with error: "
              "{response[error]}").format(room=room_verbose_name, vc_room=vc_room_id, response=response)
        )
