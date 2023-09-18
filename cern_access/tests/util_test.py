# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest
from conftest import generate_personal_data

from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.util import (get_accompanying_persons, get_last_request, sanitize_license_plate,
                                     send_adams_post_request)


class _Response:
    def json(self):
        return {'tickets': []}


@pytest.mark.parametrize(('input', 'expected'), [
    ('1234 56', '123456'),
    ('ABC DEF', 'ABCDEF'),
    ('IAm-G0D', 'IAMG0D'),
    ('ge 58 1234', 'GE581234'),
    ('BBQ PLZ-', 'BBQPLZ')
])
def test_license_plate_handling(input, expected):
    assert sanitize_license_plate(input) == expected


def test_license_plate_handling_error():
    assert sanitize_license_plate('') is None
    assert sanitize_license_plate('------') is None
    assert sanitize_license_plate('123/456') is None
    assert sanitize_license_plate('VALID 1234 \U0001F4A9') is None


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                             'personal_data': generate_personal_data(True),
                             'include_accompanying_persons': True,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')
def test_get_accompanying_persons(dummy_regform):
    reg = dummy_regform.registrations[0]
    accompanying, accompanying_persons = get_accompanying_persons(reg, get_last_request(reg.event))
    assert accompanying is True
    assert len(accompanying_persons) == 2


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                             'personal_data': generate_personal_data(True),
                             'include_accompanying_persons': False,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')
def test_get_accompanying_persons_not_include(dummy_regform):
    reg = dummy_regform.registrations[0]
    accompanying, accompanying_persons = get_accompanying_persons(reg, get_last_request(reg.event))
    assert accompanying is False
    assert len(accompanying_persons) == 0


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                             'personal_data': generate_personal_data(True),
                             'include_accompanying_persons': True,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')
def test_adams_post_request(dummy_regform, mocker):
    mocker.patch('indico_cern_access.util._send_adams_http_request', return_value=_Response())
    state, data, _ = send_adams_post_request(dummy_regform.event, dummy_regform.registrations)
    assert state == CERNAccessRequestState.active
    assert len(data) == 3


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                             'personal_data': generate_personal_data(True),
                             'include_accompanying_persons': False,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request', 'dummy_access_request')
def test_adams_post_request_not_include_accompanying(dummy_regform, mocker):
    mocker.patch('indico_cern_access.util._send_adams_http_request', return_value=_Response())
    state, data, _ = send_adams_post_request(dummy_regform.event, dummy_regform.registrations)
    assert state == CERNAccessRequestState.active
    assert len(data) == 1
