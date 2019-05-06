# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import timedelta

import pytest
from flask import g, session

from indico.modules.events.registration.controllers.display import RHRegistrationForm
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.util import create_personal_data_fields, create_registration
from indico.modules.events.requests.models.requests import Request

from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.plugin import CERNAccessPlugin


PERSONAL_DATA = {
    'request_cern_access': 1,
    'birth_date': '02/03/2000',
    'nationality': 'PT',
    'birth_place': 'Freixo de Espada as Costas'
}


@pytest.fixture
def dummy_regform(dummy_event, db):
    # event has to be in the future (badge request)
    dummy_event.start_dt += timedelta(days=1)
    dummy_event.end_dt += timedelta(days=1)
    regform = RegistrationForm(event=dummy_event, title="Dummy Registration Form", currency="CHF")
    create_personal_data_fields(regform)
    db.session.flush()
    return regform


@pytest.fixture
def dummy_registration(dummy_regform, dummy_user, db):
    registration = create_registration(dummy_regform, {
        'email': dummy_user.email,
        'first_name': dummy_user.first_name,
        'last_name': dummy_user.last_name,
        'affiliation': dummy_user.affiliation,
        'phone': dummy_user.phone,
        'position': 'Business Relationship Manager',
        'user': dummy_user
    })
    db.session.flush()
    return registration


@pytest.fixture
def mock_access_request(dummy_event, dummy_regform, dummy_user, app, request):
    data = {
        'email': dummy_user.email,
        'first_name': dummy_user.first_name,
        'last_name': dummy_user.last_name,
        'affiliation': dummy_user.affiliation,
        'phone': dummy_user.phone,
        'position': 'Business Relationship Manager',
        'user': dummy_user
    }

    data.update(request.param.get('personal_data', {}))

    with app.test_request_context(method='POST', data=data):
        session.user = dummy_user
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
                'start_dt_override': None,
                'end_dt_override': None
            }
        )

        CERNAccessRequestDefinition.send(req, {
            'start_dt_override': None,
            'end_dt_override': None
        })

        yield
