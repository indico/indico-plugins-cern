# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date

import pytest
from conftest import generate_accompanying_persons, generate_personal_data
from werkzeug.exceptions import UnprocessableEntity

from indico.modules.events.registration.util import create_registration, make_registration_schema
from indico.web.args import parser


@pytest.mark.parametrize('mock_access_request', ({
    'during_registration': True,
    'during_registration_required': False,
    'personal_data': generate_personal_data(False),
    'include_accompanying_persons': False,
}, {
    'during_registration': True,
    'during_registration_required': True,
    'personal_data': generate_personal_data(False),
    'include_accompanying_persons': False,
}), indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration(dummy_regform):
    """Data is provided during registration."""
    assert dummy_regform.cern_access_request is not None
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is not None
    assert registration.cern_access_request.nationality == 'PT'
    assert registration.cern_access_request.birth_date == date(2000, 3, 2)
    assert registration.cern_access_request.birth_place == 'Freixo de Espada as Costas'
    assert len(registration.cern_access_request.accompanying_persons) == 0


@pytest.mark.parametrize('mock_access_request', ({
    'during_registration': True,
    'during_registration_required': False,
    'include_accompanying_persons': False,
}, {
    'during_registration': True,
    'during_registration_required': False,
    'include_accompanying_persons': True,
}), indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_optional_negative(dummy_regform):
    """Data can be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is None


@pytest.mark.parametrize('mock_access_request', [{  # noqa: PT007
    'during_registration': True,
    'during_registration_required': False,
    'personal_data': generate_personal_data(True, True),
    'accompanying_persons': generate_accompanying_persons(True),
    'include_accompanying_persons': True,
}], indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_accompanying_positive(dummy_regform):
    """Data can be provided during registration (it is)."""
    assert dummy_regform.cern_access_request is not None
    schema = make_registration_schema(dummy_regform)()
    form_data = parser.parse(schema)
    registration = create_registration(dummy_regform, form_data)
    assert registration.cern_access_request is not None
    assert registration.cern_access_request.nationality == 'PT'
    assert registration.cern_access_request.birth_date == date(2000, 3, 2)
    assert registration.cern_access_request.birth_place == 'Freixo de Espada as Costas'
    assert len(registration.cern_access_request.accompanying_persons) == 2

    ac1_p = next((p for p in registration.accompanying_persons
                  if p['firstName'] == 'John' and p['lastName'] == 'Doe'), None)
    assert ac1_p is not None
    ac1 = registration.cern_access_request.accompanying_persons.get(ac1_p['id'])
    assert ac1 is not None
    assert ac1['birth_date'] == '1960-08-12'
    assert ac1['nationality'] == 'CH'
    assert ac1['birth_place'] == 'Meyrin'

    ac2_p = next((p for p in registration.accompanying_persons
                  if p['firstName'] == 'Jean' and p['lastName'] == 'Pierre'), None)
    assert ac2_p is not None
    ac2 = registration.cern_access_request.accompanying_persons.get(ac2_p['id'])
    assert ac2 is not None
    assert ac2['birth_date'] == '2010-10-10'
    assert ac2['nationality'] == 'FR'
    assert ac2['birth_place'] == 'Grenoble'


@pytest.mark.parametrize('mock_access_request', [{  # noqa: PT007
    'during_registration': True,
    'during_registration_required': True,
    'include_accompanying_persons': False,
}], indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_required_negative(dummy_regform):
    """Data must be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    with pytest.raises(UnprocessableEntity) as exc_info:
        parser.parse(schema)
    assert set(exc_info.value.data['messages']) == {
        'cern_access_nationality', 'cern_access_birth_place', 'cern_access_birth_date'
    }


@pytest.mark.parametrize('mock_access_request', [{  # noqa: PT007
    'during_registration': True,
    'during_registration_required': True,
    'accompanying_persons': generate_accompanying_persons(True),
    'include_accompanying_persons': True,
}], indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_required_accompanying_negative(dummy_regform):
    """Data must be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    with pytest.raises(UnprocessableEntity) as exc_info:
        parser.parse(schema)
    assert set(exc_info.value.data['messages']) == {
        'cern_access_nationality', 'cern_access_birth_place', 'cern_access_birth_date',
        'cern_access_accompanying_persons'
    }


@pytest.mark.parametrize('mock_access_request', [{  # noqa: PT007
    'during_registration': True,
    'during_registration_required': True,
    'personal_data': generate_personal_data(False),
    'accompanying_persons': generate_accompanying_persons(True),
    'include_accompanying_persons': True,
}], indirect=True)
@pytest.mark.usefixtures('smtp', 'mock_access_request')
def test_during_registration_required_accompanying_with_data_negative(dummy_regform):
    """Data must be provided during registration (it is not)."""
    schema = make_registration_schema(dummy_regform)()
    with pytest.raises(UnprocessableEntity) as exc_info:
        parser.parse(schema)
    assert set(exc_info.value.data['messages']) == {'cern_access_accompanying_persons'}
