# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest
from tests.conftest import RAVEM_TEST_API_ENDPOINT, RAVEM_TEST_PATH, connected_fixtures, disconnected_fixtures, gen_params
from indico_ravem.operations import connect_room, get_api
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException, RavemOperationException
from mock import MagicMock

from indico.testing.util import extract_logs
from indico.util import json


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(disconnected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_connect_room(httpretty, room_name, service_type, connected, data):
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
                        "eventName": None,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/connect",
        status=200,
        content_type="application/json",
        body=json.dumps({"result": "OK"}),
    )

    vc_room = MagicMock()
    vc_room.data = data
    vc_room.type = service_type

    connect_room(room_name, vc_room)

    assert len(httpretty.httpretty.latest_requests) == 2
    status_request = httpretty.httpretty.latest_requests[0]
    request = httpretty.last_request()

    assert request.path.startswith(RAVEM_TEST_PATH + service_type + "/connect")
    assert request.parsed_body == {"meetingId": vc_room_id, "roomName": room_name}

    assert status_request.path.startswith(RAVEM_TEST_PATH + "rooms/details")
    assert status_request.querystring == {"where": ["room_name"], "value": [room_name]}


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(disconnected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_connect_room_error(
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
                        "eventName": None,
                        "name": "videoconference",
                    }
                ],
            }
        ),
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/connect",
        status=200,
        content_type="application/json",
        body=json.dumps({"error": error_message}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room)

    assert str(excinfo.value) == "Failed to connect the room {0} to the videoconference room {1} with error: {2}"\
        .format(room_name, vc_room_id, error_message)
    log = extract_logs(caplog, one=True, name="indico.plugin.ravem")
    assert log.message == str(excinfo.value)


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_connect_room_already_connected(
    httpretty, room_name, service_type, connected, data
):
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
        RAVEM_TEST_API_ENDPOINT + service_type + "/connect",
        status=200,
        content_type="application/json",
        body=json.dumps({"error": "Call already disconnected"}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    with pytest.raises(RavemOperationException) as excinfo:
        connect_room(room_name, vc_room)

    assert str(excinfo.value) == "The room {0} is already connected to the videoconference room {1}"\
        .format(room_name, vc_room_id)
    assert excinfo.value.reason == "already-connected"


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected")
)
def test_connect_room_connected_other(
    httpretty, room_name, service_type, connected
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
    vc_room.type = service_type

    with pytest.raises(RavemOperationException) as excinfo:
        connect_room(room_name, vc_room)

    assert (
        str(excinfo.value)
        == "The room {0} is connected to another videoconference room: {1}"
        .format(room_name, different_vc_room)
    )
    assert excinfo.value.reason == "connected-other"


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    *gen_params(connected_fixtures, "room_name", "service_type", "connected", "data")
)
def test_connect_room_force_fail(
    caplog, httpretty, room_name, service_type, connected, data
):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set("polling_limit", 3)
    RavemPlugin.settings.set("polling_interval", 100)
    different_vc_room = "different_vc_room"
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

    with pytest.raises(RavemException) as excinfo:
        connect_room(room_name, vc_room, force=True)

    assert (
        str(excinfo.value)
        == "Failed to disconnect the room {0} from the videoconference room {1} "
           "with an unknown error".format(room_name, different_vc_room)
    )
    log = extract_logs(caplog, one=True, name="indico.plugin.ravem")
    assert (
        log.message
        == "Failed to disconnect the room {0} from the videoconference room {1} "
           "with an unknown error".format(room_name, different_vc_room)
    )

    assert len(httpretty.httpretty.latest_requests) == 2 + RavemPlugin.settings.get(
        "polling_limit"
    )
    request = httpretty.httpretty.latest_requests[1]
    assert request.path.startswith(RAVEM_TEST_PATH + service_type + "/disconnect")
    assert request.parsed_body == {"roomName": room_name}


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(*gen_params(connected_fixtures, "room_name", "service_type", "connected", "data"))
def test_connect_room_force_error(caplog, httpretty, room_name, service_type, connected, data):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    error_message = "Some internal error"
    different_vc_room = "different_vc_room"
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
        connect_room(room_name, vc_room, force=True)

    assert (
        str(excinfo.value)
        == "Failed to disconnect the room {0} from the videoconference room {1} with error: {2}"
        .format(room_name, different_vc_room, error_message)
    )
    log = extract_logs(caplog, one=True, name="indico.plugin.ravem")
    assert log.message == str(excinfo.value)


@pytest.mark.usefixtures("db", "mock_vc_room_id")
@pytest.mark.parametrize(*gen_params(connected_fixtures, "room_name", "service_type", "connected", "data"))
def test_connect_room_force(httpretty, room_name, service_type, connected, data):
    RavemPlugin.settings.set("api_endpoint", RAVEM_TEST_API_ENDPOINT)
    RavemPlugin.settings.set("polling_limit", 3)
    RavemPlugin.settings.set("polling_interval", 100)
    service_api = get_api(service_type)
    vc_room_id = service_api.get_room_id(data)
    different_vc_room = "different_vc_room"
    httpretty.register_uri(
        httpretty.GET,
        RAVEM_TEST_API_ENDPOINT + "rooms/details",
        status=200,
        content_type="application/json",
        responses=[
            httpretty.Response(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    "roomName": room_name,
                    "deviceType": service_type,
                    "services": [
                        {
                            "status": connected,
                            "eventName": different_vc_room,
                            "name": "videoconference",
                        }
                    ],
                })
            )] * RavemPlugin.settings.get("polling_limit") + [
            httpretty.Response(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    "roomName": room_name,
                    "deviceType": service_type,
                    "services": [
                        {
                            "status": False,
                            "eventName": None,
                            "name": "videoconference",
                        }
                    ],
                })
            )
        ]
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/disconnect",
        status=200,
        content_type="application/json",
        body=json.dumps({"result": "OK"}),
    )
    httpretty.register_uri(
        httpretty.POST,
        RAVEM_TEST_API_ENDPOINT + service_type + "/connect",
        status=200,
        content_type="application/json",
        body=json.dumps({"result": "OK"}),
    )

    vc_room = MagicMock()
    vc_room.type = service_type
    vc_room.data = data

    connect_room(room_name, vc_room, force=True)

    # status, disconnect, polling attempts and connect
    number_of_requests = 2 + RavemPlugin.settings.get("polling_limit") + 1
    assert len(httpretty.httpretty.latest_requests) == number_of_requests

    disconnect_request = httpretty.httpretty.latest_requests[1]
    assert disconnect_request.path.startswith(
        RAVEM_TEST_PATH + service_type + "/disconnect"
    )
    assert disconnect_request.parsed_body == {"roomName": room_name}

    request = httpretty.last_request()
    assert request.path.startswith(RAVEM_TEST_PATH + service_type + "/connect")
    assert request.parsed_body == {"roomName": room_name, "meetingId": vc_room_id}
