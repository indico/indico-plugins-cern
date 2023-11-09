# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest
from conftest import generate_personal_data

from indico.core import signals
from indico.modules.events.registration.util import modify_registration

from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.models.archived_requests import ArchivedCERNAccessRequest
from indico_cern_access.util import generate_access_id, get_accompanying_persons, get_last_request, grant_access


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
        res = {}
        nonces = {}
        for reg in registrations:
            res[reg.id] = {'$rc': 'test'}
            nonces[generate_access_id(reg.id)] = f'nonce#{reg.id}'
            accompanying_persons = get_accompanying_persons(reg, get_last_request(reg.event))[1]
            for person in accompanying_persons:
                res[person['id']] = {'$rc': 'test'}
                nonces[generate_access_id(person['id'])] = f"nonce#{person['id']}"
        return CERNAccessRequestState.active, res, nonces

    mock = mocker.patch('indico_cern_access.plugin.send_adams_post_request', side_effect=_mock_post, autospec=True)
    mocker.patch('indico_cern_access.util.send_adams_post_request', new=mock)
    return mock


def setup_fixtures(func):
    """Set up fixtures (utlity decorator)."""
    func = pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')(func)
    func = pytest.mark.parametrize('mock_access_request', [{
        'during_registration': True,
        'during_registration_required': True,
        'personal_data': generate_personal_data(),
        'include_accompanying_persons': False
    }, {
        'during_registration': True,
        'during_registration_required': True,
        'personal_data': generate_personal_data(),
        'include_accompanying_persons': True
    }], indirect=True)(func)
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
def test_registration_delete_permenent_active(dummy_regform, api_delete, api_post, db):
    """Hard-delete an active registration, ADAMS should be contacted (DELETE) and the request should be archived."""
    registration = dummy_regform.registrations[0]
    grant_access([registration], dummy_regform, email_body='body', email_subject='subject')
    assert api_post.call_count == 1

    signals.event.registration_deleted.send(registration, permanent=True)
    db.session.delete(registration)
    db.session.flush()
    assert ArchivedCERNAccessRequest.query.one().registration_id == registration.id
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
def test_registration_delete_permanent_inactive(dummy_regform, api_delete, api_post, db):
    """Delete an inactive registration, ADAMS should not be contacted and the request should not be archived."""
    registration = dummy_regform.registrations[0]
    num_accompanying = len(registration.cern_access_request.accompanying_persons)
    registration.cern_access_request.clear_identity_data()
    db.session.delete(registration)
    db.session.flush()
    signals.event.registration_deleted.send(registration, permanent=True)
    assert api_delete.call_count == 0
    assert api_post.call_count == 0
    assert not ArchivedCERNAccessRequest.query.has_rows()
    assert len(registration.cern_access_request.accompanying_persons) == num_accompanying


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
@pytest.mark.parametrize('mock_access_request', [{
    'during_registration': False,
    'during_registration_required': False,
    'include_accompanying_persons': True,
}], indirect=True)
def test_registration_modified_active(dummy_regform, api_delete, api_post):
    """Modify the name of the registrant, request active, ADAMS contacted (POST)."""
    registration = dummy_regform.registrations[0]
    grant_access([registration], dummy_regform, email_body='body', email_subject='subject')
    # grant_access will already contact ADAMS
    assert api_post.call_count == 1

    modify_registration(registration, {
        'first_name': 'Conan',
        'last_name': 'Osiris',
        'email': '1337@example.test'
    })
    assert api_delete.call_count == 0
    assert api_post.call_count == 2
    api_post.assert_called_with(dummy_regform.event, [registration], update=True)


@setup_fixtures
def test_registration_modified_inactive(dummy_regform, api_delete, api_post):
    """Modify the name of the registrant, request inactive, ADAMS not contacted."""
    registration = dummy_regform.registrations[0]
    modify_registration(registration, {
        'first_name': 'Conan',
        'last_name': 'Osiris',
        'email': '1337@example.test'
    })
    assert api_delete.call_count == 0
    assert api_post.call_count == 0
