from time import sleep

from indico_ravem import _
from indico_ravem.api import get_endpoint_status, disconnect_endpoint, connect_endpoint
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import get_room_endpoint, RavemException, RavemOperationException

_all__ = ('get_room_status', 'connect_room', 'disconnect_room')


def get_room_status(room_name, room_special_name=None):
    """Get the status of a room given its name.

    :param room_name: str -- The name of the room whose status is fetched
    :param room_special_name: str -- The prettier name of a room, used in the
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :returns: dict -- the status of the room with the following information:
        - `vc_room_name`: The name of the vc_room the room is connected to or
        `None` if the room is not connected.
        - `connected`: `True` if the room is connected, `False` otherwise
        - `service_type`: The type of service, given by RAVEM. Usually '"vidyo"'
        or `"other"`
        - `room_endpoint`: prefixed H323 IP or Vidyo user name of the room.
    """
    room_special_name = room_special_name or room_name
    response = get_endpoint_status(room_name)
    if 'error' in response:
        RavemPlugin.logger.error("Failed to get status of room {room} with error: {response[error]}"
                                 .format(room=room_special_name, response=response))
        raise RavemException(_("Failed to get status of room {room} with error:\n{response[error]}")
                             .format(room=room_special_name, response=response))

    result = response['result']
    if result == 'Service not found':
        RavemPlugin.logger.error("Vidyo is not supported in the room {room}".format(room=room_special_name))
        raise RavemException(_("Vidyo is not supported in the room {room}").format(room=room_special_name))

    status = next(s for s in result['services'] if s['name'] == 'videoconference')
    return {
        'vc_room_name': status['event_name'],
        'connected': status['status'] == 1,
        'service_type': status['event_type'],
        'room_endpoint': get_room_endpoint(result)
    }


def connect_room(room_name, vc_room, force=False, room_special_name=None):
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
    :param room_special_name: str -- The prettier name of a room, used in the
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :raises: RavemOperationException, RavemException
    """
    room_special_name = room_special_name or room_name
    status = get_room_status(room_name, room_special_name=room_special_name)
    if status['connected']:
        if status['vc_room_name'] == vc_room.name:
            raise RavemOperationException(
                _("The room {room} is already connected to the vidyo room {vc_room.name}")
                .format(room=room_special_name, vc_room=vc_room),
                'already-connected'
            )
        if not force:
            raise RavemOperationException(
                _("The room {room} is connected to an other Vidyo room: {status[vc_room_name]}")
                .format(room=room_special_name, status=status),
                'connected-other'
            )
        disconnect_response = disconnect_endpoint(room_name, status['vc_room_name'], status['service_type'])
        if 'error' in disconnect_response:
            RavemPlugin.logger.error(
                "Failed to disconnect the room {room} from the Vidyo room {status[vc_room_name]} with error: {response[error]}"
                .format(room=room_special_name, status=status, response=disconnect_response)
            )
            raise RavemException(
                _("Failed to disconnect the room {room} from the Vidyo room {status[vc_room_name]} with error:\n"
                  "{response[error]}").format(room=room_special_name, status=status, response=disconnect_response)
            )

        # A "success" response from RAVEM doesn't mean the room is disconnected.
        # We need to poll RAVEM for the status of the room.

        # ms in settings but time.sleep takes sec
        polling_interval = RavemPlugin.settings.get('polling_interval') / 1000.0
        for attempt in xrange(RavemPlugin.settings.get('polling_limit')):
            status = get_room_status(room_name, room_special_name=room_special_name)
            if not status['connected']:
                break
            sleep(polling_interval)
        else:
            RavemPlugin.logger.error(("Failed to disconnect the room {room} from the Vidyo room {vc_room.name} "
                                      "with an unknown error").format(room=room_special_name, vc_room=vc_room))
            raise RavemException(_("Failed to disconnect the room {room} from the Vidyo room {vc_room.name} with "
                                 "an unknown error").format(room=room_special_name, vc_room=vc_room))

    response = connect_endpoint(vc_room.data['vidyo_id'], status['room_endpoint'])

    if 'error' in response:
        RavemPlugin.logger.error(
            "Failed to connect the room {room} to the Vidyo room {vc_room.name} with error: {response[error]}"
            .format(room=room_special_name, vc_room=vc_room, response=response)
        )
        raise RavemException(
            _("Failed to connect the room {room} to the Vidyo room {vc_room.name} with error:\n{response[error]}")
            .format(room=room_special_name, vc_room=vc_room, response=response)
        )


def disconnect_room(room_name, vc_room, force=False, room_special_name=None):
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
    :param room_special_name: str -- The prettier name of a room, used in the
        error messages. For example "IT-Amphitheatre" for the room `31-3-004`.
        Defaults to the room's name

    :raises: RavemOperationException, RavemException
    """
    room_special_name = room_special_name or room_name
    status = get_room_status(room_name, room_special_name=room_special_name)
    if not status['connected']:
        raise RavemOperationException(
            _("The room {room} is already disconnected.").format(room=room_special_name),
            'already-disconnected'
        )
    if status['vc_room_name'] != vc_room.name:
        if not force:
            raise RavemOperationException(
                _("The room {room} is connected to an other Vidyo room: {status[vc_room_name]}")
                .format(room=room_special_name, status=status),
                'connected-other'
            )
        else:
            RavemPlugin.logger.info(
                ("Force disconnect of room {room} from vc_room {status[vc_room_name]} "
                 "(expected to disconnect from vc_room {vc_room.name})")
                .format(room=room_special_name, status=status, vc_room=vc_room)
            )

    response = disconnect_endpoint(room_name, status['vc_room_name'], status['service_type'])

    if 'error' in response:
        if response['error'] == 'Call already disconnected':
            raise RavemOperationException(
                _("The room {room} is already disconnected.").format(room=room_special_name),
                'already-disconnected'
            )

        RavemPlugin.logger.error(
            "Failed to disconnect the room {room} from the Vidyo room {vc_room.name} with error: {response[error]}"
            .format(room=room_special_name, vc_room=vc_room, response=response)
        )
        raise RavemException(
            _("Failed to disconnect the room {room} from the Vidyo room {vc_room.name} with error:\n{response[error]}")
            .format(room=room_special_name, vc_room=vc_room, response=response)
        )
