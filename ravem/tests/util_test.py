import pytest

from requests.auth import HTTPDigestAuth
from requests.exceptions import RequestException

from indico.testing.util import extract_logs

from indico_ravem.plugin import RavemPlugin
from indico_ravem.util import ravem_api_call


@pytest.mark.usefixtures('db')
def test_correct_auth_method(mocker):
    request = mocker.patch('indico_ravem.util.requests.get')
    ravem_api_call('test_endpoint', param1='test1', param2='test2')
    request.assert_called_once()
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
    request = mocker.patch('indico_ravem.util.requests.get')
    RavemPlugin.settings.set_multi({'username': username, 'password': password})
    ravem_api_call('test_endpoint', param1='test1', param2='test2')
    request.assert_called_once()
    auth = request.call_args[1]['auth']
    assert auth.username == username
    assert auth.password == password


@pytest.mark.usefixtures('db')
def test_accepts_json(mocker):
    request = mocker.patch('indico_ravem.util.requests.get')
    ravem_api_call('test_endpoint', param1='test1', param2='test2')
    request.assert_called_once()
    assert request.call_args[1]['headers']['Accept'] == 'application/json'


@pytest.mark.usefixtures('db')
def test_exception_is_logged(caplog, mocker):
    api_endpoint = 'htps://invalid.url'
    RavemPlugin.settings.set('api_endpoint', api_endpoint)
    with pytest.raises(RequestException):
        ravem_api_call('test_endpoint', param1='test1', param2='test2')
    log = extract_logs(caplog, one=True, name='indico.plugin.ravem')
    assert log.message.startswith("Ravem API test_endpoint call not successful")


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize(('root_endpoint', 'endpoint', 'expected_url'), (
    ('http://ravem.com/', 'final_endpoint', 'http://ravem.com/final_endpoint'),
    ('http://ravem.com/api/', 'final_endpoint', 'http://ravem.com/api/final_endpoint'),
    ('http://ravem.com/api/v2/', 'final_endpoint', 'http://ravem.com/api/v2/final_endpoint'),
    ('http://ravem.com', './final_endpoint', 'http://ravem.com/final_endpoint'),
    ('http://ravem.com/api/', './final_endpoint', 'http://ravem.com/api/final_endpoint'),
    ('http://ravem.com/api/v2/', './final_endpoint', 'http://ravem.com/api/v2/final_endpoint'),
    ('http://ravem.com', 'sub/final_endpoint', 'http://ravem.com/sub/final_endpoint'),
    ('http://ravem.com/api/', 'sub/final_endpoint', 'http://ravem.com/api/sub/final_endpoint'),
    ('http://ravem.com/api/v2/', 'sub/final_endpoint', 'http://ravem.com/api/v2/sub/final_endpoint'),
    ('http://ravem.com', './sub/final_endpoint', 'http://ravem.com/sub/final_endpoint'),
    ('http://ravem.com/api/', './sub/final_endpoint', 'http://ravem.com/api/sub/final_endpoint'),
    ('http://ravem.com/api/v2/', './sub/final_endpoint', 'http://ravem.com/api/v2/sub/final_endpoint'),
    ('http://ravem.com/', '', 'http://ravem.com/'),
    ('http://ravem.com/api/', '', 'http://ravem.com/api/'),
    ('http://ravem.com/api/v2/', '', 'http://ravem.com/api/v2/'),
))
def test_correct_api_endpoint(mocker, root_endpoint, endpoint, expected_url):
    request = mocker.patch('indico_ravem.util.requests.get')
    RavemPlugin.settings.set('api_endpoint', root_endpoint)
    ravem_api_call(endpoint, param1='test1', param2='test2')
    assert request.assert_called_once()
    assert request.call_args[0][0] == expected_url


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize('params', (
    {},
    {'p1': '1stparam'},
    {'p1': '1stparam', 'p2': '2ndparam'}
))
def test_params_generated(mocker, params):
    request = mocker.patch('indico_ravem.util.requests.get')
    ravem_api_call('test_endpoint', **params)
    assert request.assert_called_once()
    assert request.call_args[1]['params'] == params


@pytest.mark.usefixtures('db')
@pytest.mark.parametrize('method', ('put', 'PUT', 'verybad', 'VERY_BAD'))
def test_invalid_method(method):
    with pytest.raises(ValueError) as err_info:
        ravem_api_call('test_endpoint', param1='test1', param2='test2', method=method)
    assert err_info.value.message == 'Unsupported HTTP method {0}, must be GET or POST'.format(method)
