# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date

import pytest
from conftest import PERSONAL_DATA
from werkzeug.exceptions import UnprocessableEntity

from indico.modules.events.registration.util import create_registration, make_registration_schema
from indico.web.args import parser


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                             'personal_data': PERSONAL_DATA
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_positive(dummy_regform):
    """Data can be provided during registration (it is)."""
    assert dummy_regform.cern_access_request is not None
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is not None
    assert registration.cern_access_request.nationality == 'PT'
    assert registration.cern_access_request.birth_date == date(2000, 3, 2)
    assert registration.cern_access_request.birth_place == 'Freixo de Espada as Costas'


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': False,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_negative(dummy_regform):
    """Data can be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is None


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': True,
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_required_negative(dummy_regform):
    """Data must be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    with pytest.raises(UnprocessableEntity) as exc_info:
        parser.parse(schema)
    assert set(exc_info.value.data['messages']) == {
        'cern_access_nationality', 'cern_access_birth_place', 'cern_access_birth_date'
    }


@pytest.mark.parametrize('mock_access_request',
                         [{
                             'during_registration': True,
                             'during_registration_required': True,
                             'personal_data': PERSONAL_DATA
                         }],
                         indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_required_positive(dummy_regform):
    """Data must be provided during registration (it is)."""
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is not None
    assert registration.cern_access_request.nationality == 'PT'
    assert registration.cern_access_request.birth_date == date(2000, 3, 2)
    assert registration.cern_access_request.birth_place == 'Freixo de Espada as Costas'
