# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from unittest.mock import MagicMock

import pytest
from conftest import RAVEM_TEST_API_ENDPOINT, fixtures, gen_params
from responses import matchers

from indico.testing.util import extract_logs

from indico_ravem.operations import connect_room, get_api, get_room_status
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


@pytest.mark.usefixtures('db')
def test_unknown_service(mocked_responses):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    room_name = 'test'
    mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps(
            {
                'roomName': room_name,
                'deviceType': 'zoom',
                'services': [
                    {
                        'status': False,
                        'eventName': None,
                        'name': 'videoconference',
                    }
                ],
            }
        ),
    )
    vc_room = MagicMock()
    vc_room.type = 'foo'

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert str(excinfo.value) == f'{vc_room.type} is not supported in the room {room_name}'


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(
    *gen_params(fixtures, 'room_name', 'service_type', 'connected', 'data')
)
def test_get_room_status(mocked_responses, room_name, service_type, connected, data):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    req = mocked_responses.add(
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
                        'eventName': data['id'],
                        'name': 'videoconference',
                    }
                ],
            }
        ),
        match=[matchers.query_param_matcher({'where': 'room_name', 'value': room_name})]
    )

    status = get_room_status(room_name)
    assert req.call_count == 1

    assert status['room_name'] == room_name
    assert status['connected'] == connected
    assert status['vc_room_id'] == vc_room_id
    assert status['service_type'] == service_type


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(*gen_params(fixtures, 'room_name', 'error'))
def test_get_room_status_error(caplog, mocked_responses, room_name, error):
    RavemPlugin.settings.set('api_endpoint', RAVEM_TEST_API_ENDPOINT)
    req = mocked_responses.add(
        mocked_responses.GET,
        f'{RAVEM_TEST_API_ENDPOINT}/rooms/details',
        status=200,
        content_type='application/json',
        body=json.dumps({'error': error}),
        match=[matchers.query_param_matcher({'where': 'room_name', 'value': room_name})]
    )

    room_verbose_name = 'room_verbose_name'
    with pytest.raises(RavemException) as excinfo:
        get_room_status(room_name, room_verbose_name)

    assert str(excinfo.value) == f'Failed to get status of room {room_verbose_name} with error: {error}'
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == f'Failed to get status of room {room_verbose_name} with error: {error}'

    assert req.call_count == 1
