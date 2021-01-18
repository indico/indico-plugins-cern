# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import httpretty as httpretty_
import pytest
from indico_ravem.api import ZoomAPI


RAVEM_TEST_HOST = 'http://ravem.test'
RAVEM_TEST_PATH = '/api/services/'
RAVEM_TEST_API_ENDPOINT = RAVEM_TEST_HOST + RAVEM_TEST_PATH

connected_fixtures = [
    {
        'room_name': 'zoom_room',
        'error': "Room/Endpoint 'zoom_room' not found",
        'connected': True,
        'service_type': 'zoom',
        'data': {
            'vc_room_name': 'My test zoom room',
            'id': 123456
        }
    },
]
disconnected_fixtures = [
    {
        'room_name': 'zoom_room',
        'error': "Room/Endpoint 'test_room' not found",
        'connected': False,
        'service_type': 'zoom',
        'data': {
            'vc_room_name': None,
            'id': None,
        }
    },
]

fixtures = disconnected_fixtures + connected_fixtures


def gen_params(fixtures, *params):
    return params, ([fixture[param] for param in params] for fixture in fixtures)


@pytest.yield_fixture
def httpretty():
    httpretty_.reset()
    httpretty_.enable()
    try:
        yield httpretty_
    finally:
        httpretty_.disable()


@pytest.fixture(autouse=True)
def mock_vc_room_id(mocker):
    mocker.patch.object(
        ZoomAPI,
        'get_room_id',
        new=lambda cls, *args: args[0]['id']
    )
