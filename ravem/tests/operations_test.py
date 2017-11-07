# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json

import pytest
from mock import MagicMock

from indico.testing.util import extract_logs

from indico_ravem.operations import connect_room, disconnect_room, get_room_status
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException, RavemOperationException


RAVEM_TEST_HOST = 'http://ravem.test'
RAVEM_TEST_PATH = '/api/services/'
RAVEM_TEST_API_ENDPOINT = RAVEM_TEST_HOST + RAVEM_TEST_PATH

disconnected_fixtures = [
    {
        'room_name': 'test_room',
        'status': 0,
        'connected': False,
        'endpoint': lambda: 'test_user',
        'error': "Room/Endpoint 'test_room' not found",
        'vidyo_id': "123456",
        'data': {
            'vidyo_username': 'test_user',
            'vidyo_extension': '12345678',
        }
    },
    {
        'room_name': 'test_room',
        'status': 0,
        'connected': False,
        'endpoint': lambda: (str(RavemPlugin.settings.get('prefix')) + '111.222.0.42'),
        'error': "Room/Endpoint 'test_room' not found",
        'vidyo_id': "654321",
        'data': {
            'legacy_hostname': 'test_hostname',
            'legacy_ip': '111.222.0.42',
            'vidyo_extension': '12345678',
        }
    },
]
connected_fixtures = [
    {
        'room_name': 'test_room',
        'status': 1,
        'connected': True,
        'endpoint': lambda: 'test_user',
        'error': "Room/Endpoint 'test_room' not found",
        'vidyo_id': "456789",
        'data': {
            'vidyo_username': 'test_user',
            'vidyo_extension': '12345678',
            'event_name': 'test_vc_room',
            'event_type': 'vidyo'
        }
    },
    {
        'room_name': 'test_room',
        'status': 1,
        'connected': True,
        'endpoint': lambda: (str(RavemPlugin.settings.get('prefix')) + '111.222.0.42'),
        'error': "Room/Endpoint 'test_room' not found",
        'vidyo_id': "987654",
        'data': {
            'legacy_hostname': 'test_hostname',
            'legacy_ip': '111.222.0.42',
            'vidyo_extension': '12345678',
            'event_name': 'test_vc_room',
            'event_type': 'other'
        }
    },
]

fixtures = disconnected_fixtures + connected_fixtures


def _gen_params(fixtures, *params):
    return params, ([fixture[param] for param in params] for fixture in fixtures)


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(fixtures, 'room_name', 'status', 'connected', 'endpoint', 'data'))
def test_get_room_status(httpretty, room_name, status, connected, endpoint, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )

    status = get_room_status(room_name)
    assert len(httpretty.httpretty.latest_requests) == 1
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert request.querystring == {'service_name': ['videoconference'], 'where': ['room_name'], 'value': [room_name]}

    assert status['vc_room_name'] == data.get('event_name')
    assert status['connected'] == connected
    assert status['service_type'] == data.get('event_type')
    assert status['room_endpoint'] == endpoint()


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(fixtures, 'room_name', 'error'))
def test_get_room_status_error(caplog, httpretty, room_name, error):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error})
    )

    with pytest.raises(RavemException) as excinfo:
        get_room_status(room_name)

    assert excinfo.value.message == "Failed to get status of room {0} with error: {1}".format(room_name, error)
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Failed to get status of room {0} with error: {1}".format(room_name, error)

    assert len(httpretty.httpretty.latest_requests) == 1
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert request.querystring == {'service_name': ['videoconference'], 'where': ['room_name'], 'value': [room_name]}


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(fixtures, 'room_name'))
def test_get_room_status_service_not_found(caplog, httpretty, room_name):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'Service not found'})
    )

    with pytest.raises(RavemException) as excinfo:
        get_room_status(room_name)

    assert excinfo.value.message == "Vidyo is not supported in the room {0}".format(room_name)
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Vidyo is not supported in the room {0}".format(room_name)

    assert len(httpretty.httpretty.latest_requests) == 1
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert request.querystring == {'service_name': ['videoconference'], 'where': ['room_name'], 'value': [room_name]}


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room(httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    disconnect_room(room_name, vc_room)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [data.get('event_name')]
    assert request.querystring == query

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room_error(caplog, httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    error_message = 'Some internal error'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error_message})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert excinfo.value.message == "Failed to disconnect the room {0} from the Vidyo room {1} with error: {2}" \
                                    .format(room_name, data.get('event_name'), error_message)
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Failed to disconnect the room {0} from the Vidyo room {1} with error: {2}" \
                          .format(room_name, data.get('event_name'), error_message)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [data.get('event_name')]
    assert request.querystring == query

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(disconnected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room_not_connected(httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemOperationException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert excinfo.value.message == "The room {room} is already disconnected.".format(room=room_name)
    assert excinfo.value.reason == 'already-disconnected'

    assert len(httpretty.httpretty.latest_requests) == 1
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert request.querystring == {'service_name': ['videoconference'], 'where': ['room_name'], 'value': [room_name]}

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room_already_disconnected(httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': 'Call already disconnected'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemOperationException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert excinfo.value.message == "The room {room} is already disconnected.".format(room=room_name)
    assert excinfo.value.reason == 'already-disconnected'

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [data.get('event_name')]
    assert request.querystring == query

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room_connected_other(httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': different_vc_room,
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemOperationException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert excinfo.value.message == "The room {0} is connected to an other Vidyo room: {1}".format(room_name,
                                                                                                   different_vc_room)
    assert excinfo.value.reason == 'connected-other'

    assert len(httpretty.httpretty.latest_requests) == 1
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert request.querystring == {'service_name': ['videoconference'], 'where': ['room_name'], 'value': [room_name]}

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_disconnect_room_force(caplog, httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': different_vc_room,
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    disconnect_room(room_name, vc_room, force=True)

    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Force disconnect of room {0} from vc_room {1} (expected to disconnect from vc_room {2})" \
                          .format(room_name, different_vc_room, data.get('event_name'))

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [different_vc_room]
    assert request.querystring == query

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(disconnected_fixtures, 'room_name', 'status', 'endpoint', 'vidyo_id', 'data'))
def test_connect_room(httpretty, room_name, status, endpoint, vidyo_id, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')
    vc_room.data = {'vidyo_id': vidyo_id}

    connect_room(room_name, vc_room)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/connect')
    assert request.querystring == {
        'vidyo_room_id': [vidyo_id],
        'query': [endpoint()],
    }

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(disconnected_fixtures, 'room_name', 'status', 'endpoint', 'vidyo_id', 'data'))
def test_connect_room_error(caplog, httpretty, room_name, status, endpoint, vidyo_id, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    error_message = 'Some internal error'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error_message})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')
    vc_room.data = {'vidyo_id': vidyo_id}

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room)

    assert excinfo.value.message == "Failed to connect the room {0} to the Vidyo room {1} with error: {2}" \
                                    .format(room_name, data.get('event_name'), error_message)
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Failed to connect the room {0} to the Vidyo room {1} with error: {2}" \
                          .format(room_name, data.get('event_name'), error_message)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/connect')
    assert request.querystring == {
        'vidyo_room_id': [vidyo_id],
        'query': [endpoint()],
    }

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'vidyo_id', 'data'))
def test_connect_room_already_connected(httpretty, room_name, status, vidyo_id, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': data.get('event_name'),
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': 'Call already disconnected'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')
    vc_room.data = {'vidyo_id': vidyo_id}

    with pytest.raises(RavemOperationException) as excinfo:
        connect_room(room_name, vc_room)

    assert excinfo.value.message == "The room {0} is already connected to the vidyo room {1}" \
                                    .format(room_name, vc_room.name)
    assert excinfo.value.reason == 'already-connected'

    assert len(httpretty.httpretty.latest_requests) == 1
    status_request = httpretty.last_request()

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_connect_room_connected_other(httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': different_vc_room,
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemOperationException) as excinfo:
        connect_room(room_name, vc_room)

    assert excinfo.value.message == "The room {0} is connected to an other Vidyo room: {1}".format(room_name,
                                                                                                   different_vc_room)
    assert excinfo.value.reason == 'connected-other'

    assert len(httpretty.httpretty.latest_requests) == 1
    status_request = httpretty.last_request()

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_connect_room_force_fail(caplog, httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set('polling_limit', 3)
    RavemPlugin.settings.set('polling_interval', 100)
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': different_vc_room,
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert excinfo.value.message == "Failed to disconnect the room {0} from the Vidyo room {1} with an unknown error" \
                                    .format(room_name, data.get('event_name'))
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Failed to disconnect the room {0} from the Vidyo room {1} with an unknown error" \
                          .format(room_name, data.get('event_name'))

    # status, disconnect and polling attempts
    assert len(httpretty.httpretty.latest_requests) == 2 + RavemPlugin.settings.get('polling_limit')
    for i, status_request in enumerate(httpretty.httpretty.latest_requests):
        if i == 1:  # disconnect request
            continue

        assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
        assert status_request.querystring == {
            'service_name': ['videoconference'],
            'where': ['room_name'],
            'value': [room_name]
        }

    request = httpretty.httpretty.latest_requests[1]
    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [different_vc_room]
    assert request.querystring == query


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'data'))
def test_connect_room_force_error(caplog, httpretty, room_name, status, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    error_message = 'Some internal error'
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        status=200,
        content_type='application/json',
        body=json.dumps({
            'result': {
                'name': room_name,
                'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                'services': [{
                    'status': status,
                    'event_name': different_vc_room,
                    'name': 'videoconference',
                    'event_type': data.get('event_type')
                }],
                'common_name': data.get('common_name')
            }})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error_message})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert excinfo.value.message == "Failed to disconnect the room {0} from the Vidyo room {1} with error: {2}" \
                                    .format(room_name, different_vc_room, error_message)
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "Failed to disconnect the room {0} from the Vidyo room {1} with error: {2}" \
                          .format(room_name, different_vc_room, error_message)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [different_vc_room]
    assert request.querystring == query

    assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
    assert status_request.querystring == {
        'service_name': ['videoconference'],
        'where': ['room_name'],
        'value': [room_name]
    }


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*_gen_params(connected_fixtures, 'room_name', 'status', 'endpoint', 'vidyo_id', 'data'))
def test_connect_room_force(httpretty, room_name, status, endpoint, vidyo_id, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set('polling_limit', 3)
    RavemPlugin.settings.set('polling_interval', 100)
    different_vc_room = 'different_vc_room'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + 'getstatus',
        responses=[
            httpretty.Response(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'result': {
                        'name': room_name,
                        'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                        'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                        'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                        'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                        'services': [{
                            'status': status,
                            'event_name': different_vc_room,
                            'name': 'videoconference',
                            'event_type': data.get('event_type')
                        }],
                        'common_name': data.get('common_name')
                    }})
            )] * RavemPlugin.settings.get('polling_limit') + [
            httpretty.Response(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    'result': {
                        'name': room_name,
                        'vc_endpoint_legacy_hostname': data.get('legacy_hostname'),
                        'vc_endpoint_vidyo_username': data.get('vidyo_username'),
                        'vc_endpoint_legacy_ip': data.get('legacy_ip'),
                        'vc_endpoint_vidyo_extension': data.get('vidyo_extension'),
                        'services': [{
                            'status': 0,
                            'event_name': None,
                            'name': 'videoconference',
                            'event_type': None
                        }],
                        'common_name': data.get('common_name')
                    }})
            )
        ]
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + 'videoconference/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'})
    )

    vc_room = MagicMock()
    vc_room.name = data.get('event_name')
    vc_room.data = {'vidyo_id': vidyo_id}

    connect_room(room_name, vc_room, force=True)

    # status, disconnect, polling attempts and connect
    number_of_requests = 2 + RavemPlugin.settings.get('polling_limit') + 1
    assert len(httpretty.httpretty.latest_requests) == number_of_requests
    for i, status_request in enumerate(httpretty.httpretty.latest_requests):
        if i == 1 or i == number_of_requests - 1:  # disconnect/connect request
            continue

        assert status_request.path.startswith(RAVEM_TEST_PATH + 'getstatus')
        assert status_request.querystring == {
            'service_name': ['videoconference'],
            'where': ['room_name'],
            'value': [room_name]
        }

    disconnect_request = httpretty.httpretty.latest_requests[1]
    assert disconnect_request.path.startswith(RAVEM_TEST_PATH + 'videoconference/disconnect')
    query = {
        'type': [data.get('event_type')],
        'where': ['room_name'],
        'value': [room_name],
    }
    if data.get('event_type') == 'vidyo':
        query['vidyo_room_name'] = [different_vc_room]
    assert disconnect_request.querystring == query

    request = httpretty.last_request()
    assert request.path.startswith(RAVEM_TEST_PATH + 'videoconference/connect')
    assert request.querystring == {
        'vidyo_room_id': [vidyo_id],
        'query': [endpoint()],
    }
