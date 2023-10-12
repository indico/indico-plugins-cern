# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from unittest.mock import MagicMock, Mock

import pytest
from flask import request
from werkzeug.exceptions import NotFound

from indico.core.errors import IndicoError
from indico.modules.rb import Room

from indico_ravem.controllers import RHRavemConnectRoom, RHRavemDisconnectRoom, RHRavemRoomStatus
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException


def event_vc_room(vc_room=None, link_object=False, event_id=None,
                  rb_room=False, rb_room_gen_name=None, rb_room_name=None):
    event_vc_room = MagicMock()
    event_vc_room.vc_room = vc_room

    if link_object or event_id or rb_room or rb_room_gen_name or rb_room_name:
        event_vc_room.link_object = MagicMock()
    else:
        event_vc_room.link_object = None
        return event_vc_room

    event_vc_room.link_object.event = MagicMock(id=event_id) if event_id else None

    if rb_room or rb_room_gen_name or rb_room_name:
        event_vc_room.link_object.room = MagicMock(Room)

        type(event_vc_room.link_object.room).name = Room.name
        event_vc_room.link_object.room.generate_name = MagicMock(return_value=rb_room_gen_name)
        event_vc_room.link_object.room.verbose_name = rb_room_name

    else:
        event_vc_room.link_object.room = None

    return event_vc_room


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_vc_room_not_found(mocker, rh_class):
    id_ = 123456
    request.view_args['event_vc_room_id'] = id_

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = None
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(NotFound) as excinfo:
            rh._process_args()

    assert excinfo.value.description == f'Event VC Room not found for id {id_}'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_vc_room_without_link_object(mocker, rh_class):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room()
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._process_args()

    assert str(excinfo.value) == f'Event VC Room ({id_}) is not linked to anything'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_link_object_without_conference(mocker, rh_class):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(link_object=True)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._process_args()

    assert str(excinfo.value) == f'Event VC Room ({id_}) does not have an event'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_id_not_matching_event_id(mocker, rh_class):
    id_ = 123456
    event_id = 1111
    evcr_event_id = '2222'

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(event_id=evcr_event_id)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._process_args()

    assert str(excinfo.value) == f'Event VC Room ({id_}) does not have an event with the id {evcr_event_id}'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_invalid_room(mocker, rh_class):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(event_id=event_id)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._process_args()

    assert str(excinfo.value) == f'Event VC Room ({id_}) is not linked to an event with a room'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_invalid_room_name(mocker, rh_class):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(event_id=event_id, rb_room=True)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._process_args()

    assert str(excinfo.value) == f'Event VC Room ({id_}) is not linked to an event with a valid room'


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation_name', 'args', 'kwargs', 'fixture'), (
    (RHRavemRoomStatus, 'get_room_status', ['room_name', 'room_verbose_name'], [], {
        'room_name': '513-B-22',
        'room_verbose_name': 'Personalized name',
        'vc_room': Mock(type='zoom'),
    }),
    (RHRavemConnectRoom, 'connect_room', ['room_name', 'vc_room'], ['room_verbose_name', 'force'], {
        'room_name': '513-B-22',
        'room_verbose_name': 'Personalized name',
        'vc_room': Mock(type='zoom'),
        'force': True
    }),
    (RHRavemDisconnectRoom, 'disconnect_room', ['room_name', 'vc_room'], ['room_verbose_name', 'force'], {
        'room_name': '513-B-22',
        'room_verbose_name': 'Personalized name',
        'vc_room': Mock(type='zoom'),
        'force': True
    })
))
def test_operation_called_with_correct_args(mocker, rh_class, operation_name, args, kwargs, fixture):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(vc_room=fixture.get('vc_room'), event_id=event_id,
                                                rb_room_gen_name=fixture['room_name'],
                                                rb_room_name=fixture['room_verbose_name'])

    operation = mocker.patch('indico_ravem.controllers.' + operation_name, return_value={})

    rh = rh_class()
    if fixture.get('force'):
        request.args = {'force': '1'}

    with RavemPlugin.instance.plugin_context():
        rh._process_args()
        rh._process()

    assert operation.call_count == 1
    call_args = operation.call_args[0]
    call_kwargs = operation.call_args[1]
    for i, val in enumerate(fixture.get(k) for k in args):
        assert call_args[i] == val
    assert call_kwargs == {k: fixture.get(k) for k in kwargs}


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation_name', 'err_reason', 'err_message'), (
    (RHRavemConnectRoom, 'connect_room', 'connect-other', 'The room is connected to another room'),
    (RHRavemDisconnectRoom, 'disconnect_room', 'already-disconnected', 'The room is already disconnected'),
))
def test_operation_exception_is_handled(mocker, rh_class, operation_name, err_reason, err_message):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    op_mock = mocker.patch('indico_ravem.controllers.' + operation_name)
    op_mock.side_effect = RavemException(err_message, err_reason)

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(vc_room='<vc_room_object(id:6789)>', event_id=event_id,
                                                rb_room_gen_name='513-B-22', rb_room_name='Personalized name')

    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._process_args()
        response = rh._process()

    data = json.loads(response.get_data())
    assert data['success'] is False
    assert data['reason'] == err_reason
    assert data['message'] == err_message


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation_name', 'err_message'), (
    (RHRavemRoomStatus, 'get_room_status', 'This is just annoying'),
    (RHRavemConnectRoom, 'connect_room', 'The room does not exist'),
    (RHRavemDisconnectRoom, 'disconnect_room', 'Well this is unexpected'),
))
def test_exception_is_handled(mocker, rh_class, operation_name, err_message):
    id_ = 123456
    event_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['event_id'] = event_id

    op_mock = mocker.patch('indico_ravem.controllers.' + operation_name)
    op_mock.side_effect = RavemException(err_message)

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation')
    mock.query.get.return_value = event_vc_room(vc_room=Mock(type='zoom'), event_id=event_id,
                                                rb_room_gen_name='513-B-22', rb_room_name='Personalized name')

    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._process_args()
        response = rh._process()

    data = json.loads(response.get_data())
    assert data['success'] is False
    assert data['message'] == err_message


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_exception_raised_on_unauthorized_access(mocker, rh_class):
    mock = mocker.patch('indico_ravem.controllers.has_access')
    mock.return_value = False

    rh = rh_class()
    rh.event_vc_room = event_vc_room()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(RavemException) as excinfo:
            rh._check_access()

    assert str(excinfo.value) == 'Not authorized to access the room with RAVEM'
