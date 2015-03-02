from indico_ravem.util import ravem_api_call

__all__ = ('get_endpoint_status', 'disconnect_endpoint', 'connect_endpoint')


def get_endpoint_status(room_name):
    """Returns the status of an physical room.

    This call returns the status of a room equipped with Vidyo capable device

    :param room_name: str -- the name of the physical room

    :returns: dict -- the status of the room as a JSON response according to the
              RAVEM API.
    """
    return ravem_api_call('getstatus', method='GET', service_name='videoconference', where='room_name', value=room_name)


def disconnect_endpoint(room_name, vc_room_name, service_type):
    """Disconnects a physical room from a vidyo room using the RAVEM API.

    This call will return "OK" as a result immediately if RAVEM can (or has
    started to) perform the operation. This does not mean the operation has
    actually succeeded. One should pool for the status of the room afterwards
    using the `get_endpoint_status` method after some delay to allow the
    operation to be performed.

    :param room_name: str -- the name of the physical room
    :param vc_room_name: str -- The Vidyo room name (which is recommended to
                         disconnect the physical room from the Vidyo room in
                         case the service type is Vidyo.)
    :param service_type: str -- The endpoint type (usually `vidyo` or `other`)

    :returns: dict -- {'result': 'OK'} if the operation "succeeds", raises a
              RavemAPIException otherwise.
    """
    params = {
        'method': 'POST',
        'where': 'room_name',
        'value': room_name,
        'type': service_type
    }
    if service_type == 'vidyo':
        params['vidyo_room_name'] = vc_room_name

    return ravem_api_call('videoconference/disconnect', **params)


def connect_endpoint(vidyo_room_id, query):
    """Connects a physical room to a Vidyo room using the RAVEM API.

    This call will return "OK" as a result immediately if RAVEM can (or has
    started to) perform the operation. This does not mean the operation has
    actually succeeded. One should pool for the status of the room afterwards
    using the `get_endpoint_status` method after some delay to allow the
    operation to be performed..

    :param vidyo_room_id: str -- target Vidyo room ID
    :param query: str -- search query passed to RAVEM to allow it to find the
                  physical room from Vidyo. Usually, simply the room's endpoint
                  as specified in the room's status data.

    :returns: dict -- {'result': 'OK'} if the operation "succeeds", raises a
              RavemAPIException otherwise.
    """
    return ravem_api_call('videoconference/connect', method='POST', vidyo_room_id=vidyo_room_id, query=query)
