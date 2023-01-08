# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from unittest.mock import MagicMock

import pytest
from conftest import RAVEM_TEST_API_ENDPOINT, RAVEM_TEST_PATH, connected_fixtures, disconnected_fixtures, gen_params

from indico.testing.util import extract_logs

from indico_ravem.operations import disconnect_room, get_api
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_disconnect_room(httpretty, room_name, service_type, connected, data):
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
                        "eventName": vc_room_id,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/disconnect",
        status=200,
        content_type="application/json",
        body=json.dumps({"result": "OK"}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    disconnect_room(room_name, vc_room)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + service_type + "/disconnect")
    assert request.parsed_body == {"roomName": room_name}

    assert status_request.path.startswith(RAVEM_TEST_PATH + "rooms/details")
    assert status_request.querystring == {"where": ["room_name"], "value": [room_name]}


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_disconnect_room_error(
    caplog, httpretty, room_name, service_type, connected, data
):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    error_message = "Some internal error"
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
                        "eventName": vc_room_id,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/disconnect",
        status=200,
        content_type="application/json",
        body=json.dumps({"error": error_message}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert (
        str(excinfo.value)
        == "Failed to disconnect the room {} from the videoconference room {} with error: {}".format(
            room_name, vc_room_id, error_message
        )
    )
    log = extract_logs(caplog, one=True, name="indico.plugin.ravem")
    assert log.message == str(excinfo.value)


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(disconnected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_disconnect_room_not_connected(
    httpretty, room_name, service_type, connected, data
):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
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
                        "eventName": None,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert str(excinfo.value) == f"The room {room_name} is already disconnected."
    assert excinfo.value.reason == "already-disconnected"


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_disconnect_room_connected_other(
    httpretty, room_name, service_type, connected, data
):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    different_vc_room = 123
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
                        "eventName": different_vc_room,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )

    vc_room = MagicMock()
    vc_room.name = room_name
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        disconnect_room(room_name, vc_room)

    assert str(excinfo.value) == \
        f"The room {room_name} is connected to another videoconference room: {different_vc_room}"
    assert excinfo.value.reason == "connected-other"

    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/disconnect",
        status=200,
        content_type="application/json",
        body=json.dumps({"result": "OK"}),
    )

    disconnect_room(room_name, vc_room, force=True)
