import pytest

from urlparse import urljoin

from indico_ravem.plugin import RavemPlugin
from indico_ravem.api import get_endpoint_status, disconnect_endpoint, connect_endpoint

room_name = '513-r-055'
vidyo_room_id = 'vidyoroom1'
service_type = 'vidyo'
query = room_name

fixtures = [
    {
        'api_fn': get_endpoint_status,
        'method': 'get',
        'args': [room_name],
        'expected_endpoint': 'getstatus',
        'expected_params': {'service_name': 'videoconference', 'where': 'room_name', 'value': room_name}
    }, {
        'api_fn': connect_endpoint,
        'method': 'post',
        'args': [vidyo_room_id, query],
        'expected_endpoint': 'videoconference/connect',
        'expected_params': {'vidyo_room_id': vidyo_room_id, 'query': query}
    }, {
        'api_fn': disconnect_endpoint,
        'method': 'post',
        'args': [room_name, service_type],
        'expected_endpoint': 'videoconference/disconnect',
        'expected_params': {'where': 'room_name', 'value': room_name, 'vidyo_room_name': room_name,
                            'type': service_type}
    }
]


def _gen_params(*params):
    return (params, ([fixture[param] for param in params] for fixture in fixtures))


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params('api_fn', 'method', 'args', 'expected_endpoint'))
def test_correct_endpoint(mocker, api_fn, method, args, expected_endpoint):
    request = mocker.patch('indico_ravem.util.requests.' + method)
    expected_endpoint = urljoin(RavemPlugin.settings.get('api_endpoint'), expected_endpoint)
    api_fn(*args)
    request.assert_called_once()
    assert request.call_args[0][0] == expected_endpoint


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params('api_fn', 'method', 'args', 'expected_params'))
def test_correct_params(mocker, api_fn, method, args, expected_params):
    request = mocker.patch('indico_ravem.util.requests.' + method)
    api_fn(*args)
    request.assert_called_once()
    assert request.call_args[1]['params'] == expected_params
