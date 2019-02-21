# This file is part of Indico.
# Copyright (C) 2002 - 2018 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from datetime import date

import pytest

from indico.modules.events.registration.util import create_registration, make_registration_form

from .conftest import PERSONAL_DATA


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
