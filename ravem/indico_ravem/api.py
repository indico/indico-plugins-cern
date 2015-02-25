"""
API calls for RAVEM. Each call returns a Response object.

The following calls are available:
get_legacy_endpoint_status --  get the status of a room with a legacy Vidyo endpoint
get_vidyo_panorama_status --  get the status of a room with a panorama Vidyo endpoint
connect_room -- connect to a Vidyo legacy or panorama endpoint using the RAVEM API
disconnect_legacy_endpoint -- disconnect from a Vidyo legacy endpoint using the RAVEM API
disconnect_vidyo_panorama -- disconnect from a Vidyo legacy endpoint using the RAVEM API
"""
from indico_ravem.util import ravem_api_call

__all__ = ('get_endpoint_status', 'disconnect_endpoint', 'connect_endpoint')


def get_endpoint_status(room_name):
    """Returns the status of an endpoint.

    This call returns the status of a room equipped with either a legacy device
    or a vidyo panorama endpoint depending on the type.

    :param endpoint_type: IndicoEnum -- the type of endpoint, either legacy or
    Vidyo panorama as defined in indico_ravem.util.EndpointType.
    :param endpoint_identifier: str -- the identifier of the endpoint either the
    room's IP for legacy endpoint or the Vidyo username for the room for Vidyo
    panorama endpoints

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('getstatus', method='GET', service_name='videoconference', where='room_name', value=room_name)


def disconnect_endpoint(room_name, vc_room_name, service_type):
    """Disconnects from a room using the RAVEM API.

    This call will disconnect from a room with either a legacy endpoint or a
    Vidyo panorama endpoint based on the Vidyo room id and a search query to
    find the room from the Vidyo user API.

    :param endpoint_type: IndicoEnum -- the type of endpoint, either legacy or
    Vidyo panorama as defined in indico_ravem.util.EndpointType.
    :param endpoint_identifier: str -- the identifier of the endpoint either the
    room's IP for legacy endpoint or the Vidyo username for the room for Vidyo
    panorama endpoints
    :param service_type: str -- The endpoint type (usually `vidyo` or `other`)
    :param room_name: str -- The Vidyo room name (used as the query to find the
    room)

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
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
    """Connects to a room using the RAVEM API.

    This call will establish a connection to a room using a legacy or Vidyo
    panorama endpoint based on the Vidyo room id and a search query to find the
    room from the Vidyo user API.

    :param vidyo_room_id: str -- target Vidyo room ID
    :param query: str -- search query to find the conference room from Vidyo
    User API

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('videoconference/connect', method='POST', vidyo_room_id=vidyo_room_id, query=query)
