# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from unittest.mock import MagicMock

import pytest
from requests.auth import HTTPDigestAuth
from requests.exceptions import HTTPError, Timeout

from indico.testing.util import extract_logs

from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import RavemAPIException, has_access, ravem_api_call


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize('method', ('get', 'post'))
def test_correct_http_method(mocker, method):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    ravem_api_call('test_endpoint', method=method, param1='test1', param2='test2')

    assert request.call_count == 1
    assert request.call_args[0][0] == method


@pytest.mark.usefixtures('db')
def test_correct_auth_method(mocker):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    ravem_api_call('test_endpoint', param1='test1', param2='test2')

    assert request.call_count == 1
    assert isinstance(request.call_args[1]['auth'], HTTPDigestAuth)


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(('username', 'password'), (
    ('foo', 'bar'),
    ('foo', ''),
    ('', 'bar'),
    ('', ''),
    ('foo', None)
))
def test_correct_auth_credentials(mocker, username, password):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    RavemPlugin.settings.set_multi({'username': username, 'password': password})
    ravem_api_call('test_endpoint', param1='test1', param2='test2')

    assert request.call_count == 1
    auth = request.call_args[1]['auth']
    assert auth.username == username
    assert auth.password == password


@pytest.mark.usefixtures('db')
def test_accepts_json(mocker):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    ravem_api_call('test_endpoint', param1='test1', param2='test2')

    assert request.call_count == 1
    assert request.call_args[1]['headers']['Accept'] == 'application/json'


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(('root_endpoint', 'endpoint', 'expected_url'), (
    ('https://ravem.test/', 'final_endpoint', 'https://ravem.test/final_endpoint'),
    ('https://ravem.test/api/', 'final_endpoint', 'https://ravem.test/api/final_endpoint'),
    ('https://ravem.test/api/v2/', 'final_endpoint', 'https://ravem.test/api/v2/final_endpoint'),
    ('https://ravem.test', './final_endpoint', 'https://ravem.test/final_endpoint'),
    ('https://ravem.test/api/', './final_endpoint', 'https://ravem.test/api/final_endpoint'),
    ('https://ravem.test/api/v2/', './final_endpoint', 'https://ravem.test/api/v2/final_endpoint'),
    ('https://ravem.test', 'sub/final_endpoint', 'https://ravem.test/sub/final_endpoint'),
    ('https://ravem.test/api/', 'sub/final_endpoint', 'https://ravem.test/api/sub/final_endpoint'),
    ('https://ravem.test/api/v2/', 'sub/final_endpoint', 'https://ravem.test/api/v2/sub/final_endpoint'),
    ('https://ravem.test', './sub/final_endpoint', 'https://ravem.test/sub/final_endpoint'),
    ('https://ravem.test/api/', './sub/final_endpoint', 'https://ravem.test/api/sub/final_endpoint'),
    ('https://ravem.test/api/v2/', './sub/final_endpoint', 'https://ravem.test/api/v2/sub/final_endpoint'),
    ('https://ravem.test/', '', 'https://ravem.test/'),
    ('https://ravem.test/api/', '', 'https://ravem.test/api/'),
    ('https://ravem.test/api/v2/', '', 'https://ravem.test/api/v2/'),
))
def test_correct_api_endpoint(mocker, root_endpoint, endpoint, expected_url):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    RavemPlugin.settings.set('api_endpoint', root_endpoint)
    ravem_api_call(endpoint, param1='test1', param2='test2')

    assert request.call_count == 1
    assert request.call_args[0][1] == expected_url


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize('params', (
    {},
    {'p1': '1stparam'},
    {'p1': '1stparam', 'p2': '2ndparam'}
))
def test_params_generated(mocker, params):
    request = mocker.patch('indico_ravem.util.requests.request')
    response = MagicMock()
    response.json.return_value = {'result': 'test'}
    response.raise_for_status.return_value = False
    request.return_value = response

    ravem_api_call('test_endpoint', **params)

    assert request.call_count == 1
    assert request.call_args[1]['params'] == params


@pytest.mark.usefixtures('db')
def test_raises_timeout(mocker):
    request = mocker.patch('indico_ravem.util.requests.request')
    request.side_effect = Timeout('Timeout test error message', request=request)

    with pytest.raises(Timeout) as excinfo:
        ravem_api_call('test_endpoint')

    assert str(excinfo.value) == "Timeout while contacting the room."
    assert request.call_count == 1


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(('method', 'params'), (
    ('get', {}),
    ('post', {}),
    ('get', {'p1': '1stparam'}),
    ('post', {'p1': '1stparam'}),
    ('get', {'p1': '1stparam', 'p2': '2ndparam'}),
    ('post', {'p1': '1stparam', 'p2': '2ndparam'})
))
def test_unexpected_exception_is_logged(mocker, caplog, method, params):
    request = mocker.patch('indico_ravem.util.requests.request')
    request.side_effect = IndexError('this is unexpected')

    with pytest.raises(IndexError) as excinfo:
        ravem_api_call('test_endpoint', method=method, **params)

    assert str(excinfo.value) == 'this is unexpected'
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == "failed call: {} {} with {}: {}".format(method.upper(), 'test_endpoint', params,
                                                                  'this is unexpected')
    assert request.call_count == 1


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(('method', 'params'), (
    ('get', {}),
    ('post', {}),
    ('get', {'p1': '1stparam'}),
    ('post', {'p1': '1stparam'}),
    ('get', {'p1': '1stparam', 'p2': '2ndparam'}),
    ('post', {'p1': '1stparam', 'p2': '2ndparam'})
))
def test_http_error_is_logged(mocker, caplog, method, params):
    request = mocker.patch('indico_ravem.util.requests.request')
    request.method = method.upper()
    request.url = RavemPlugin.settings.get('api_endpoint') + 'test_endpoint'
    response = MagicMock()
    response.raise_for_status.side_effect = HTTPError('Well this is embarrassing')
    response.request = request
    response.url = response.request.url
    request.return_value = response

    with pytest.raises(HTTPError) as excinfo:
        ravem_api_call('test_endpoint', method=method, **params)

    assert str(excinfo.value) == 'Well this is embarrassing'
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == '{} {} failed with {}'.format(
        method.upper(), RavemPlugin.settings.get('api_endpoint') + 'test_endpoint', 'Well this is embarrassing')

    assert request.call_count == 1


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize('method', ('GET', 'POST', 'Get', 'Post', 'get', 'post'))
def test_invalid_json_respons_is_handled(mocker, caplog, method):
    request = mocker.patch('indico_ravem.util.requests.request')
    request.method = method.upper()
    request.url = RavemPlugin.settings.get('api_endpoint') + 'test_endpoint'
    response = MagicMock()
    response.request = request
    response.url = response.request.url
    response.json.return_value = {'bad': 'json'}
    response.raise_for_status.return_value = False
    request.return_value = response

    with pytest.raises(RavemAPIException) as excinfo:
        ravem_api_call('test_endpoint', method=method)

    err_msg = '{} {} returned json without a result or error: {}'.format(
        method.upper(), RavemPlugin.settings.get('api_endpoint') + 'test_endpoint', {'bad': 'json'})
    assert str(excinfo.value) == err_msg
    assert excinfo.value.endpoint == 'test_endpoint'
    assert excinfo.value.response == response

    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message == err_msg

    assert request.call_count == 1


@pytest.mark.usefixtures('db')
def test_unlinked_event_vc_room_has_no_access():
    event_vc_room = MagicMock()
    event_vc_room.link_object = None

    assert not has_access(event_vc_room)


@pytest.mark.usefixtures('db', 'request_context')
def test_unlinked_room_has_no_access(mocker):
    session = mocker.patch('indico_ravem.util.session')
    session.user = 'Guinea Pig'

    event_vc_room = MagicMock()
    event_vc_room.link_object.room = None

    assert not has_access(event_vc_room)


@pytest.mark.usefixtures('db', 'request_context')
def test_room_not_vidyo_capable_has_no_access(mocker):
    session = mocker.patch('indico_ravem.util.session')
    session.user = 'Guinea Pig'

    event_vc_room = MagicMock()
    event_vc_room.link_object.room.has_equipment = MagicMock(return_value=False)

    assert not has_access(event_vc_room)

    event_vc_room.link_object.room.has_equipment.assert_called_once_with('Vidyo')


@pytest.mark.usefixtures('db', 'request_context')
def test_check_if_current_user_is_room_owner(mocker):
    session = mocker.patch('indico_ravem.util.session')
    session.user = 'Guinea Pig'
    request = mocker.patch('indico_ravem.util.request')
    request.remote_addr = '111.222.123.123'
    retrieve_principal = mocker.patch('indico_ravem.util.retrieve_principal')
    retrieve_principal.side_effect = lambda x, **kw: x

    event_vc_room = MagicMock()
    event_vc_room.link_object.room.has_equipment = MagicMock(return_value=True)
    event_vc_room.link_object.room.get_attribute_value.return_value = request.remote_addr
    event_vc_room.vc_room.data.get.return_value = session.user
    event_vc_room.event.can_manage.return_value = False

    assert has_access(event_vc_room)

    event_vc_room.vc_room.data.get.assert_called_once_with('owner')
    retrieve_principal.assert_called_once_with(event_vc_room.vc_room.data.get.return_value)


@pytest.mark.usefixtures('db', 'request_context')
def test_check_if_current_user_can_modify(mocker):
    request = mocker.patch('indico_ravem.util.request')
    request.remote_addr = '111.222.123.123'
    session = mocker.patch('indico_ravem.util.session')
    session.user = 'Guinea Pig'
    mocker.patch('indico_ravem.util.retrieve_principal')

    event_vc_room = MagicMock()
    event_vc_room.link_object.room.has_equipment = MagicMock(return_value=True)
    event_vc_room.link_object.room.get_attribute_value.return_value = request.remote_addr
    event_vc_room.event.can_manage.return_value = True

    assert has_access(event_vc_room)

    event_vc_room.event.can_manage.assert_called_once_with(session.user)


@pytest.mark.usefixtures('db', 'request_context')
def test_check_if_request_from_room(mocker):
    mocker.patch('indico_ravem.util.session')
    mocker.patch('indico_ravem.util.retrieve_principal')
    request = mocker.patch('indico_ravem.util.request')
    request.remote_addr = '111.222.123.123'

    event_vc_room = MagicMock()
    event_vc_room.link_object.room.has_equipment = MagicMock(return_value=True)
    event_vc_room.link_object.room.get_attribute_value.return_value = request.remote_addr
    event_vc_room.event.can_manage.return_value = True

    assert has_access(event_vc_room)

    event_vc_room.link_object.room.get_attribute_value.assert_called_once_with('ip', '')


@pytest.mark.usefixtures('db', 'request_context')
def test_check_basic_user_outside_room(mocker):
    mocker.patch('indico_ravem.util.session')
    mocker.patch('indico_ravem.util.retrieve_principal')
    request = mocker.patch('indico_ravem.util.request')
    request.remote_addr = '111.222.123.123'

    event_vc_room = MagicMock()
    event_vc_room.link_object.room.has_equipment = MagicMock(return_value=True)
    event_vc_room.link_object.room.get_attribute_value.return_value = request.remote_addr
    event_vc_room.event.can_manage.return_value = True

    assert has_access(event_vc_room)
