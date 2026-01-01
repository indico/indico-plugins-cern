# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date, timedelta

import pytest
from flask import g, session

from indico.modules.events.registration.controllers.display import RHRegistrationForm
from indico.modules.events.registration.models.form_fields import RegistrationFormField
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.items import RegistrationFormSection
from indico.modules.events.registration.util import create_personal_data_fields, create_registration
from indico.modules.events.requests.models.requests import Request

from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState
from indico_cern_access.plugin import CERNAccessPlugin
from indico_cern_access.util import get_last_request


_PERSONAL_DATA = {
    'cern_access_request_cern_access': True,
    'cern_access_birth_date': '2000-03-02',
    'cern_access_nationality': 'PT',
    'cern_access_birth_place': 'Freixo de Espada as Costas'
}


def generate_accompanying_persons(temporary_id=False):
    return [
        {
            'id': 'new:1' if temporary_id else 'a237e079-c208-42f4-ba8a-dbe2330413a5',
            'firstName': 'John',
            'lastName': 'Doe',
        },
        {
            'id': 'new:2' if temporary_id else '364f94d3-4745-464a-a6d8-401394a4c7fe',
            'firstName': 'Jean',
            'lastName': 'Pierre',
        },
    ]


def generate_personal_data(accompanying=False, temporary_id=False):
    data = _PERSONAL_DATA.copy()
    if accompanying:
        data['cern_access_accompanying_persons'] = {
            'new:1' if temporary_id else 'a237e079-c208-42f4-ba8a-dbe2330413a5': {
                'birth_date': '1960-08-12',
                'nationality': 'CH',
                'birth_place': 'Meyrin'
            },
            'new:2' if temporary_id else '364f94d3-4745-464a-a6d8-401394a4c7fe': {
                'birth_date': '2010-10-10',
                'nationality': 'FR',
                'birth_place': 'Grenoble'
            }
        }
    return data


@pytest.fixture
def dummy_regform(dummy_event, db):
    # event has to be in the future (badge request)
    dummy_event.start_dt += timedelta(days=1)
    dummy_event.end_dt += timedelta(days=1)
    regform = RegistrationForm(event=dummy_event, title='Dummy Registration Form', currency='CHF')
    create_personal_data_fields(regform)
    db.session.flush()
    return regform


@pytest.fixture
def accompanying_persons_field(db, dummy_regform):
    section = RegistrationFormSection(
        registration_form=dummy_regform,
        title='dummy_section',
        is_manager_only=False
    )
    db.session.add(section)
    db.session.flush()
    field = RegistrationFormField(
        input_type='accompanying_persons',
        title='Field',
        parent=section,
        registration_form=dummy_regform
    )
    field.field_impl.form_item.data = {
        'max_persons': 0,
        'persons_count_against_limit': False,
    }
    field.versioned_data = field.field_impl.form_item.data
    db.session.flush()
    return field.html_field_name


@pytest.fixture
def mock_access_request(dummy_event, dummy_regform, dummy_user, accompanying_persons_field, app, request):
    data = {
        'email': dummy_user.email,
        'first_name': dummy_user.first_name,
        'last_name': dummy_user.last_name,
    }

    data.update(request.param.get('personal_data', {}))
    if 'accompanying_persons' in request.param:
        data[accompanying_persons_field] = request.param['accompanying_persons']

    with app.test_request_context(method='POST', json=data):
        session.set_session_user(dummy_user)
        session.lang = 'en_GB'

        CERNAccessPlugin.settings.acls.add_principal('authorized_users', dummy_user)

        g.rh = RHRegistrationForm()
        g.rh.regform = dummy_regform

        req = Request(
            event=dummy_event,
            definition=CERNAccessRequestDefinition(),
            created_by_user=dummy_user,
            data={
                'comment': 'no comments',
                'regforms': [dummy_regform.id],
                'during_registration': request.param['during_registration'],
                'during_registration_required': request.param['during_registration_required'],
                'include_accompanying_persons': request.param['include_accompanying_persons'],
                'start_dt_override': None,
                'end_dt_override': None
            }
        )

        CERNAccessRequestDefinition.send(req, {
            'start_dt_override': None,
            'end_dt_override': None
        })

        yield


@pytest.fixture
def dummy_access_request(dummy_regform, accompanying_persons_field):
    """Create a registration and corresponding request."""
    reg = create_registration(dummy_regform, {
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'Dude',
        accompanying_persons_field: generate_accompanying_persons()
    })
    accompanying = get_last_request(dummy_regform.event).data.get('include_accompanying_persons', False)
    accompaning_persons = generate_personal_data(True)['cern_access_accompanying_persons'] if accompanying else {}
    reg.cern_access_request = CERNAccessRequest(birth_date=date(2000, 1, 1),
                                                nationality='XX',
                                                birth_place='bar',
                                                license_plate=None,
                                                request_state=CERNAccessRequestState.not_requested,
                                                accompanying_persons=accompaning_persons)
