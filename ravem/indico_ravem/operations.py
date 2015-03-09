from time import sleep

from indico_ravem import _
from indico_ravem.api import get_endpoint_status, disconnect_endpoint, connect_endpoint
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import get_room_endpoint, RavemException, RavemOperationException

_all__ = ('get_room_status', 'connect_room', 'disconnect_room')


def get_room_status(room_name, room_special_name=None):
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
                "Failed to disconnect the room {room} from the Vidyo room {vc_room.name} with error: {response[error]}"
                .format(room=room_special_name, vc_room=vc_room, response=disconnect_response)
            )
            raise RavemException(
                _("Failed to disconnect the room {room} from the Vidyo room {vc_room.name} with error:\n"
                  "{response[error]}").format(room=room_special_name, vc_room=vc_room, response=disconnect_response)
            )

        # A "success" response from RAVEM doesn't mean the room is disconnected.
        # We need to poll RAVEM for the status of the room.
        for attempt in xrange(RavemPlugin.settings.get('polling_limit')):
            status = get_room_status(room_name, room_special_name=room_special_name)
            if not status['connected']:
                break
            sleep(RavemPlugin.settings.get('polling_interval') / 1000.0)  # ms in settings but time.sleep takes sec
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
                 "(expected to disconnect from vc_room {vc_room.name}")
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
