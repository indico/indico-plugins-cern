import pytest

from urlparse import urljoin

from indico_ravem.plugin import RavemPlugin
from indico_ravem.api import (get_legacy_endpoint_status,
                              get_vidyo_panorama_endpoint_status,
                              disconnect_legacy_endpoint,
                              disconnect_vidyo_panorama_endpoint,
                              connect_to_endpoint)

room_ip = '112.122.132.142'
vidyo_panorama_id = 'user3242'
vidyo_room_id = '3242'
service_type = 'videoconference'
room_name = 'main_auditorium'
query = 'room_name:{0}'.format(room_name)

fixtures = [
    {
        'api_fn': get_legacy_endpoint_status,
        'args': [room_ip],
        'expected_endpoint': 'getstatus',
        'expected_params': {'where': 'vc_endpoint_legacy_ip', 'value': room_ip}
    }, {
        'api_fn': get_vidyo_panorama_endpoint_status,
        'args': [vidyo_panorama_id],
        'expected_endpoint': 'getstatus',
        'expected_params': {'where': 'vc_endpoint_vidyo_username', 'value': vidyo_panorama_id}
    }, {
        'api_fn': disconnect_legacy_endpoint,
        'args': [room_ip, service_type, room_name],
        'expected_endpoint': 'videoconference/disconnect',
        'expected_params': {'where': 'vc_endpoint_legacy_ip', 'value': room_ip, 'vidyo_room_name': room_name,
                            'type': service_type}
    }, {
        'api_fn': disconnect_vidyo_panorama_endpoint,
        'args': [vidyo_panorama_id, service_type, room_name],
        'expected_endpoint': 'videoconference/disconnect',
        'expected_params': {'where': 'vc_endpoint_vidyo_username', 'value': vidyo_panorama_id,
                            'vidyo_room_name': room_name, 'type': service_type}
    }, {
        'api_fn': connect_to_endpoint,
        'args': [vidyo_room_id, query],
        'expected_endpoint': 'videoconference/connect',
        'expected_params': {'vidyo_room_id': vidyo_room_id, 'query': query}
    }
]


def _gen_params(*required_params):
    return (required_params, ([v for k, v in fixture.iteritems() if k in required_params] for fixture in fixtures))


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params('api_fn', 'args', 'expected_endpoint'))
def test_correct_endpoint(mocker, api_fn, args, expected_endpoint):
    request = mocker.patch('indico_ravem.util.requests.get')
    expected_endpoint = urljoin(RavemPlugin.settings.get('api_endpoint'), expected_endpoint)
    api_fn(*args)
    request.assert_called_once()
    assert request.call_args[0][0] == expected_endpoint


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params('api_fn', 'args', 'expected_params'))
def test_correct_params(mocker, api_fn, args, expected_params):
    request = mocker.patch('indico_ravem.util.requests.get')
    api_fn(*args)
    request.assert_called_once()
    assert request.call_args[1]['params'] == expected_params
