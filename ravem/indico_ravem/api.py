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

__all__ = ['get_legacy_endpoint_status', 'get_vidyo_panorama_endpoint_status', 'disconnect_legacy_endpoint',
           'disconnect_vidyo_panorama_endpoint', 'connect_to_endpoint']


def get_legacy_endpoint_status(room_ip):
    """Returns the status of a legacy endpoint.

    This call returns the status of a room equipped with a legacy device.

    :param room_ip: str -- the IP of the room

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('getstatus', where='vc_endpoint_legacy_ip', value=room_ip)


def get_vidyo_panorama_endpoint_status(vidyo_panorama_id):
    """Returns the status of a Vidyo panorama endpoint.

    This call returns the status of a room equipped with a Vidyo panorama
    device.

    :param vidyo_panorama_id: str -- the Vidyo user name of the room

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('getstatus', where='vc_endpoint_vidyo_username', value=vidyo_panorama_id)


def disconnect_legacy_endpoint(room_ip, service_type, room_name):
    """Disconnects from a room with a legacy endpoint using the RAVEM API.

    This call will disconnect from a room with a legacy endpoint based on the
    Vidyo room id and a search query to find the room from the Vidyo user API.

    :param room_ip: str -- target Vidyo room ID
    :param service_type: str -- The endpoint type (usually `vidyo` or `other`)
    :param room_name: str -- The Vidyo room name

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('videoconference/disconnect', where='vc_endpoint_legacy_ip',
                          value=room_ip, vidyo_room_name=room_name, type=service_type)


def disconnect_vidyo_panorama_endpoint(vidyo_panorama_id, service_type, room_name):
    """Disconnects from a room with a Vidyo panorama endpoint using the RAVEM API.

    This call will disconnect from a room with a Vidyo panorama endpoint based
    on the Vidyo room id and a search query to find the room from the Vidyo user
    API.

    :param vidyo_panorama_id: str -- target Vidyo user name
    :param service_type: str -- The endpoint type (usually `vidyo` or `other`)
    :param room_name: str -- The Vidyo room name

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    return ravem_api_call('videoconference/disconnect', where='vc_endpoint_vidyo_username',
                          value=vidyo_panorama_id, vidyo_room_name=room_name, type=service_type)


def connect_to_endpoint(vidyo_room_id, query):
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
    return ravem_api_call('videoconference/connect', vidyo_room_id=vidyo_room_id, query=query)
