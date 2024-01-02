# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from unittest.mock import MagicMock

import pytest
from conftest import RAVEM_TEST_API_ENDPOINT, connected_fixtures, disconnected_fixtures, gen_params
from responses import matchers

from indico.testing.util import extract_logs

from indico_ravem.operations import connect_room, get_api
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(disconnected_fixtures, 'room_name', 'service_type', 'connected', 'data')
)
def test_connect_room(mocked_responses, room_name, service_type, connected, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    req_details = mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': None,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
        match=[matchers.query_param_matcher({'where': 'room_name', 'value': room_name})]
    )
    req_connect = mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'}),
        match=[matchers.json_params_matcher({'meetingId': vc_room_id, 'roomName': room_name})]
    )

    vc_room = MagicMock()
    vc_room.data = data
    vc_room.type = service_type

    connect_room(room_name, vc_room)

    assert req_details.call_count == 1
    assert req_connect.call_count == 1


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(disconnected_fixtures, 'room_name', 'service_type', 'connected', 'data')
)
def test_connect_room_error(
    caplog, mocked_responses, room_name, service_type, connected, data
):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    error_message = 'Some internal error'
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': None,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
    )
    mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error_message}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room)

    assert str(excinfo.value) == \
        f'Failed to connect the room {room_name} to the videoconference room {vc_room_id} with error: {error_message}'
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == str(excinfo.value)


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, 'room_name', 'service_type', 'connected', 'data')
)
def test_connect_room_already_connected(
    mocked_responses, room_name, service_type, connected, data
):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': vc_room_id,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room)

    assert str(excinfo.value) == f'The room {room_name} is already connected to the videoconference room {vc_room_id}'
    assert excinfo.value.reason == 'already-connected'


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, 'room_name', 'service_type', 'connected')
)
def test_connect_room_connected_other(
    mocked_responses, room_name, service_type, connected
):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    different_vc_room = 123
    mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': different_vc_room,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
    )

    vc_room = MagicMock()
    vc_room.type = service_type

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room)

    assert str(excinfo.value) == \
        f'The room {room_name} is connected to another videoconference room: {different_vc_room}'
    assert excinfo.value.reason == 'connected-other'


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, 'room_name', 'service_type', 'connected', 'data')
)
def test_connect_room_force_fail(
    caplog, mocked_responses, room_name, service_type, connected, data
):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set('polling_limit', 3)
    RavemPlugin.settings.set('polling_interval', 100)
    different_vc_room = 'different_vc_room'
    req_details = mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': different_vc_room,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
        match=[matchers.query_param_matcher({'where': 'room_name', 'value': room_name})]
    )
    req_disconnect = mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'}),
        match=[matchers.json_params_matcher({'roomName': room_name})]
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert (
        str(excinfo.value)
        == f'Failed to disconnect the room {room_name} from the videoconference room {different_vc_room} '
           'with an unknown error'
    )
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert (
        log.message
        == f'Failed to disconnect the room {room_name} from the videoconference room {different_vc_room} '
           'with an unknown error'
    )

    assert req_disconnect.call_count == 1
    assert req_details.call_count == 1 + RavemPlugin.settings.get('polling_limit')


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*gen_params(connected_fixtures, 'room_name', 'service_type', 'connected', 'data'))
def test_connect_room_force_error(caplog, mocked_responses, room_name, service_type, connected, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    error_message = 'Some internal error'
    different_vc_room = 'different_vc_room'
    mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': connected,
                        'eventName': different_vc_room,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
        match=[matchers.query_param_matcher({'where': 'room_name', 'value': room_name})]
    )
    mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error_message}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert (
        str(excinfo.value)
        == f'Failed to disconnect the room {room_name} from the videoconference room '
           f'{different_vc_room} with error: {error_message}'
    )
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == str(excinfo.value)


@pytest.mark.usefixtures('db', 'mock_vc_room_id')
@pytest.mark.parametrize(*gen_params(connected_fixtures, 'room_name', 'service_type', 'connected', 'data'))
def test_connect_room_force(mocked_responses, room_name, service_type, connected, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set('polling_limit', 3)
    RavemPlugin.settings.set('polling_interval', 100)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    different_vc_room = 'different_vc_room'

    details_resps = [(
        200,
        {'Content-type': 'application/json'},
        json.dumps({
            'roomName': room_name,
            'deviceType': service_type,
            'services': [
                {
                    'status': connected,
                    'eventName': different_vc_room,
                    'name': 'videoconference',
                }
            ],
        })
    )] * RavemPlugin.settings.get('polling_limit') + [
        (
            200,
            {'Content-type': 'application/json'},
            json.dumps({
                'roomName': room_name,
                'deviceType': service_type,
                'services': [
                    {
                        'status': False,
                        'eventName': None,
                        'name': 'videoconference',
                    }
                ],
            })
        )
    ]

    mocked_responses.add_callback(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        callback=lambda req: details_resps.pop(0),
    )
    req_disconnect = mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/disconnect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'}),
        match=[matchers.json_params_matcher({'roomName': room_name})]
    )
    req_connect = mocked_responses.add(
        mocked_responses.POST,
        f'{RAVEM_TEST_API_ENDPOINT}/{service_type}/connect',
        status=200,
        content_type='application/json',
        body=json.dumps({'result': 'OK'}),
        match=[matchers.json_params_matcher({'roomName': room_name, 'meetingId': vc_room_id})]
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    connect_room(room_name, vc_room, force=True)

    # status, disconnect, polling attempts and connect
    assert not details_resps  # all resps consumed
    assert req_disconnect.call_count == 1
    assert req_connect.call_count == 1
