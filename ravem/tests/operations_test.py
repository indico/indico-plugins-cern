# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from unittest.mock import MagicMock

import pytest

from indico.testing.util import extract_logs

from conftest import RAVEM_TEST_API_ENDPOINT, RAVEM_TEST_PATH, fixtures, gen_params
from indico_ravem.operations import connect_room, get_api, get_room_status
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


@pytest.mark.usefixtures("db")
def test_unknown_service(httpretty):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    room_name = 'test'
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + "rooms/details",
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "roomName": room_name,
                "deviceType": 'zoom',
                "services": [
                    {
                        "status": False,
                        "eventName": None,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )
    vc_room = MagicMock()
    vc_room.type = 'foo'

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert str(excinfo.value) == f"{vc_room.type} is not supported in the room {room_name}"


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(fixtures, "room_name", "service_type", "connected", "data")
)
def test_get_room_status(httpretty, room_name, service_type, connected, data):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + "rooms/details",
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "roomName": room_name,
                "deviceType": service_type,
                "services": [
                    {
                        "status": connected,
                        "eventName": data["id"],
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )

    status = get_room_status(room_name)
    assert len(httpretty.httpretty.latest_requests) == 1
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + "rooms/details")
    assert request.querystring == {"where": ["room_name"], "value": [room_name]}

    assert status["room_name"] == room_name
    assert status["connected"] == connected
    assert status["vc_room_id"] == vc_room_id
    assert status["service_type"] == service_type


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(*gen_params(fixtures, "room_name", "error"))
def test_get_room_status_error(caplog, httpretty, room_name, error):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + "rooms/details",
        status=200,
        content_type="application/json",
        body=json.dumps({"error": error}),
    )

    room_verbose_name = "room_verbose_name"
    with pytest.raises(RavemException) as excinfo:
        get_room_status(room_name, room_verbose_name)

    assert str(excinfo.value) == f"Failed to get status of room {room_verbose_name} with error: {error}"
    log = extract_logs(caplog, one=True, name="indico.plugin.ravem")
    assert log.message == f"Failed to get status of room {room_verbose_name} with error: {error}"

    assert len(httpretty.httpretty.latest_requests) == 1
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + "rooms/details")
    assert request.querystring == {"where": ["room_name"], "value": [room_name]}
