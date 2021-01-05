# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import pytest

from indico.core import signals
from indico.modules.events.registration.util import create_registration, make_registration_form, modify_registration

from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.util import grant_access

from conftest import PERSONAL_DATA


@pytest.fixture
def api_delete(mocker):
    """Mock up DELETE request to ADAMS."""
    mock = mocker.patch('indico_cern_access.plugin.send_adams_delete_request', autospec=True)
    mocker.patch('indico_cern_access.util.send_adams_delete_request', new=mock)
    return mock


@pytest.fixture
def api_post(mocker):
    """Mock up POST request to ADAMS."""
    def _mock_post(event, registrations, **kwargs):
        return CERNAccessRequestState.active, {reg.id: {'$rc': 'test'} for reg in registrations}

    mock = mocker.patch('indico_cern_access.plugin.send_adams_post_request', side_effect=_mock_post, autospec=True)
    mocker.patch('indico_cern_access.util.send_adams_post_request', new=mock)
    return mock


@pytest.fixture
def dummy_access_request(dummy_regform):
    """Create a registration and corresponding request."""
    form = make_registration_form(dummy_regform)(csrf_enabled=False)
    form.validate()
    return create_registration(dummy_regform, form.data).cern_access_request


def setup_fixtures(func):
    """Set up fixtures (utlity decorator)."""
    func = pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')(func)
    func = pytest.mark.parametrize('mock_access_request',
                                   [{
                                       'during_registration': True,
                                       'during_registration_required': True,
                                       'personal_data': PERSONAL_DATA
                                   }],
                                   indirect=True)(func)
    return func


@setup_fixtures
def test_registration_delete_active(dummy_regform, api_delete, api_post):
    """Delete an active registration, ADAMS should be contacted (DELETE)."""
    registration = dummy_regform.registrations[0]
    grant_access([registration], dummy_regform, email_body='body', email_subject='subject')
    assert api_post.call_count == 1

    registration.is_deleted = True
    signals.event.registration_deleted.send(registration)
    assert api_delete.call_count == 1
    assert api_post.call_count == 1


@setup_fixtures
def test_registration_delete_inactive(dummy_regform, api_delete, api_post):
    """Delete an inactive registration, ADAMS should not be contacted."""
    registration = dummy_regform.registrations[0]
    registration.is_deleted = True
    signals.event.registration_deleted.send(registration)
    assert api_delete.call_count == 0
    assert api_post.call_count == 0


@setup_fixtures
def test_registration_form_deleted(dummy_regform, api_delete, api_post):
    """Delete a registration form, ADAMS should be contacted (DELETE)."""
    dummy_regform.is_deleted = True
    signals.event.registration_form_deleted.send(dummy_regform)
    assert api_delete.call_count == 1
    assert api_post.call_count == 0


@setup_fixtures
def test_event_deleted(dummy_regform, api_delete, api_post):
    """Delete the event, ADAMS should be contacted (DELETE)."""
    dummy_regform.event.delete('Unit tests')
    assert api_delete.call_count == 1
    assert api_post.call_count == 0


@pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')
@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': False,
                             'during_registration_required': False,
                             'personal_data': {}
                         }],
                         indirect=True)
def test_registration_modified_active(dummy_regform, api_delete, api_post):
    """Modify the name of the registrant, request active, ADAMS contacted (POST)."""
    registration = dummy_regform.registrations[0]
    grant_access([registration], dummy_regform, email_body='body', email_subject='subject')
    # grant_access will already contact ADAMS
    assert api_post.call_count == 1

    modify_registration(registration, {
        'first_name': 'Conan',
        'last_name': 'Osiris',
        'email': '1337@example.com'
    })
    api_delete.call_count == 0
    assert api_post.call_count == 2
    api_post.assert_called_with(dummy_regform.event, [registration], update=True)


@setup_fixtures
def test_registration_modified_inactive(dummy_regform, api_delete, api_post):
    """Modify the name of the registrant, request inactive, ADAMS not contacted."""
    registration = dummy_regform.registrations[0]
    modify_registration(registration, {
        'first_name': 'Conan',
        'last_name': 'Osiris',
        'email': '1337@example.com'
    })
    assert api_delete.call_count == 0
    assert api_post.call_count == 0
