# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date

import pytest
from conftest import PERSONAL_DATA

from indico.modules.events.registration.util import create_registration, make_registration_form


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

    form = make_registration_form(dummy_regform)(csrf_enabled=False)
    assert form.validate()

    registration = create_registration(dummy_regform, form.data)
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
    form = make_registration_form(dummy_regform)(csrf_enabled=False)
    assert form.validate()

    registration = create_registration(dummy_regform, form.data)
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
    form = make_registration_form(dummy_regform)(csrf_enabled=False)
    assert not form.validate()


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
    form = make_registration_form(dummy_regform)(csrf_enabled=False)
    assert form.validate()

    registration = create_registration(dummy_regform, form.data)
    assert registration.cern_access_request is not None
    assert registration.cern_access_request.nationality == 'PT'
    assert registration.cern_access_request.birth_date == date(2000, 3, 2)
    assert registration.cern_access_request.birth_place == 'Freixo de Espada as Costas'
