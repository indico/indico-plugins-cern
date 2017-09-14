import json

import pytest
from flask import request
from mock import MagicMock
from werkzeug.exceptions import NotFound

from indico.core.errors import IndicoError

from indico_ravem.controllers import RHRavemConnectRoom, RHRavemDisconnectRoom, RHRavemRoomStatus
from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemException, RavemOperationException


def event_vc_room(vc_room=None, link_object=False, conf_id=None,
                  rb_room=False, rb_room_gen_name=None, rb_room_name=None):
    event_vc_room = MagicMock()
    event_vc_room.vc_room = vc_room

    if link_object or conf_id or rb_room or rb_room_gen_name or rb_room_name:
        event_vc_room.link_object = MagicMock()
    else:
        event_vc_room.link_object = None
        return event_vc_room

    event_vc_room.link_object.event = MagicMock(id=conf_id) if conf_id else None

    if rb_room or rb_room_gen_name or rb_room_name:
        event_vc_room.link_object.room = MagicMock()

        event_vc_room.link_object.room.generate_name.return_value = rb_room_gen_name
        event_vc_room.link_object.room.name = rb_room_name

    else:
        event_vc_room.link_object.room = None

    return event_vc_room


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_vc_room_not_found(mocker, rh_class):
    id_ = 123456
    request.view_args['event_vc_room_id'] = id_

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = None
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(NotFound) as excinfo:
            rh._checkParams()

    assert excinfo.value.description == "Event VC Room not found for id {0}".format(id_)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_vc_room_without_link_object(mocker, rh_class):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room()
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._checkParams()

    assert excinfo.value.message == "Event VC Room ({0}) is not linked to anything".format(id_)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_link_object_without_conference(mocker, rh_class):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(link_object=True)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._checkParams()

    assert excinfo.value.message == "Event VC Room ({0}) does not have an event".format(id_)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_event_id_not_matching_conf_id(mocker, rh_class):
    id_ = 123456
    conf_id = 1111
    evcr_conf_id = '2222'

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(conf_id=evcr_conf_id)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._checkParams()

    assert excinfo.value.message == "Event VC Room ({0}) does not have an event with the id {1}" \
                                    .format(id_, evcr_conf_id)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_invalid_room(mocker, rh_class):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(conf_id=conf_id)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._checkParams()

    assert excinfo.value.message == "Event VC Room ({0}) is not linked to an event with a room".format(id_)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_invalid_room_name(mocker, rh_class):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(conf_id=conf_id, rb_room=True)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        with pytest.raises(IndicoError) as excinfo:
            rh._checkParams()

    assert excinfo.value.message == "Event VC Room ({0}) is not linked to an event with a valid room".format(id_)


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_special_name_different_from_name(mocker, rh_class):
    id_ = 123456
    conf_id = 1111
    room_name = '513-B-22'
    room_special_name = 'Personalized name'

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(conf_id=conf_id, rb_room_gen_name=room_name, rb_room_name=room_special_name)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()

    assert rh.room_name != room_special_name
    assert rh.room_name == room_name
    assert rh.room_special_name == room_special_name


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize('rh_class', (RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom))
def test_default_special_name(mocker, rh_class):
    id_ = 123456
    conf_id = 1111
    room_name = '513-B-22'

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    mock = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    mock.return_value = event_vc_room(conf_id=conf_id, rb_room_gen_name=room_name)
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()

    assert rh.room_name == room_name
    assert rh.room_special_name == room_name


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation_name', 'args', 'kwargs', 'fixture'), (
    (RHRavemRoomStatus, 'get_room_status', ['room_name'], ['room_special_name'], {
        'room_name': '513-B-22',
        'room_special_name': 'Personalized name'
    }),
    (RHRavemConnectRoom, 'connect_room', ['room_name', 'vc_room'], ['room_special_name', 'force'], {
        'room_name': '513-B-22',
        'room_special_name': 'Personalized name',
        'vc_room': '<vc_room_object(id:6789)>',
        'force': True
    }),
    (RHRavemDisconnectRoom, 'disconnect_room', ['room_name', 'vc_room'], ['room_special_name', 'force'], {
        'room_name': '513-B-22',
        'room_special_name': 'Personalized name',
        'vc_room': '<vc_room_object(id:6789)>',
        'force': True
    })
))
def test_operation_called_with_correct_args(mocker, rh_class, operation_name, args, kwargs, fixture):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    evcr_query = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    evcr_query.return_value = event_vc_room(vc_room=fixture.get('vc_room'), conf_id=conf_id,
                                            rb_room_gen_name=fixture['room_name'],
                                            rb_room_name=fixture['room_special_name'])

    operation = mocker.patch('indico_ravem.controllers.' + operation_name)

    rh = rh_class()
    if fixture.get('force'):
        request.args = {'force': '1'}

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()
        rh._process()

    assert operation.call_count == 1
    call_args = operation.call_args[0]
    call_kwargs = operation.call_args[1]
    for i, val in enumerate(fixture.get(k) for k in args):
        assert call_args[i] == val
    assert call_kwargs == {k: fixture.get(k) for k in kwargs}


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation'), (
    (RHRavemRoomStatus, {
        'name': 'get_room_status',
        'return_value': {
            'vc_room_name': '513-B-22',
            'connected': True,
            'service_type': 'vidyo',
            'room_endpoint': 'vidyo_username'
        }
    }),
    (RHRavemConnectRoom, {'name': 'connect_room'}),
    (RHRavemDisconnectRoom, {'name': 'disconnect_room'}),
))
def test_successful_operation(mocker, rh_class, operation):
    id_ = 123456
    conf_id = 1111
    room_name = '513-B-22'
    room_special_name = 'Personalized name'

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    evcr_query = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    evcr_query.return_value = event_vc_room(conf_id=conf_id, rb_room_gen_name=room_name, rb_room_name=room_special_name)

    op_mock = mocker.patch('indico_ravem.controllers.' + operation['name'])
    op_mock.return_value = dict(operation.get('return_value', {}))
    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()
        response = rh._process()

    data = json.loads(response.get_data())
    assert data['success'] is True
    del data['success']
    assert data == operation.get('return_value', {})


@pytest.mark.usefixtures('db', 'request_context')
@pytest.mark.parametrize(('rh_class', 'operation_name', 'err_reason', 'err_message'), (
    (RHRavemConnectRoom, 'connect_room', 'connect-other', 'The room is connected to another room'),
    (RHRavemDisconnectRoom, 'disconnect_room', 'already-disconnected', 'The room is already disconnected'),
))
def test_operation_exception_is_handled(mocker, rh_class, operation_name, err_reason, err_message):
    id_ = 123456
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    op_mock = mocker.patch('indico_ravem.controllers.' + operation_name)
    op_mock.side_effect = RavemOperationException(err_message, err_reason)

    evcr_query = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    evcr_query.return_value = event_vc_room(vc_room='<vc_room_object(id:6789)>', conf_id=conf_id,
                                            rb_room_gen_name='513-B-22', rb_room_name='Personalized name')

    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()
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
    conf_id = 1111

    request.view_args['event_vc_room_id'] = id_
    request.view_args['confId'] = conf_id

    op_mock = mocker.patch('indico_ravem.controllers.' + operation_name)
    op_mock.side_effect = RavemException(err_message)

    evcr_query = mocker.patch('indico_ravem.controllers.VCRoomEventAssociation.find_one')
    evcr_query.return_value = event_vc_room(vc_room='<vc_room_object(id:6789)>', conf_id=conf_id,
                                            rb_room_gen_name='513-B-22', rb_room_name='Personalized name')

    rh = rh_class()

    with RavemPlugin.instance.plugin_context():
        rh._checkParams()
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
            rh._checkProtection()

    assert excinfo.value.message == "Not authorized to access the room with RAVEM"
