from indico_ravem.api import get_endpoint_status, disconnect_endpoint, connect_endpoint
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException

_all__ = ('get_room_status', 'connect_room', 'disconnect_room')


def get_room_status(room_name):
    response = get_endpoint_status(room_name)
    if 'error' in response:
        raise RavemException('failed to get status of room {room_name} with error: {response[error]}'
                             .format(room_name=room_name, response=response))

    result = response['result']
    if result == 'Service not found':
        raise RavemException('video conferencing not supported')

    status = next(s for s in result['services'] if s['name'] == 'videoconference')
    return {
        'vc_room_name': status['event_name'],
        'connected': status['status'] == 1,
        'service_type': status['event_type'],
        'room_endpoint': result['vc_endpoint_legacy_ip'] or result['vc_endpoint_vidyo_username']
    }


def connect_room(room_name, vc_room, force=False):
    status = get_room_status(room_name)
    if status['connected']:
        if status['vc_room_name'] == vc_room.name:
            raise RavemException('already connected')
        if not force:
            raise RavemException('room connected to an other vc_room: {status[vc_room_name]}'.format(status=status))
        disconnect_room(room_name, vc_room, force=True)

    response = connect_endpoint(vc_room.vidyo_room_id, status['room_endpoint'])

    if 'error' in response:
        raise RavemException(
            'failed to connect room {room_name} to vc_room {vc_room.name} with error: {response[error]}'
            .format(room_name=room_name, vc_room=vc_room, response=response)
        )
    return response


def disconnect_room(room_name, vc_room, force=False):
    status = get_room_status(room_name)
    if not status['connected']:
        raise RavemException('already disconnected')
    if status['vc_room_name'] != vc_room.name:
        if not force:
            raise RavemException('room connected to an other vc_room: {status[vc_room_name]}'.format(status=status))
        else:
            RavemPlugin.logger.info(
                ("Force disconnect of room {room} from vc_room {status[vc_room_name]} "
                 "(expected to disconnect from vc_room {vc_room.name}")
                .format(room=room_name, status=status, vc_room=vc_room)
            )

    response = disconnect_endpoint(room_name, status['service_type'])

    if 'error' in response:
        raise RavemException(
            'failed to disconnect room {room_name} to vc_room {vc_room.name} with error: {response[error]}'
            .format(room_name=room_name, vc_room=vc_room, response=response)
        )
    return response
