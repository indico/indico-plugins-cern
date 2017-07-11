from __future__ import unicode_literals

import hashlib
import json
import random
import string
import requests
from indico.core.db import db

from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.modules.events.requests.models.requests import RequestState
from indico.util.string import remove_accents, unicode_to_ascii

from indico_cern_access.models.access_request_regforms import CERNAccessRequestRegForm
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState


def get_requested_forms(event):
    return (RegistrationForm.query.with_parent(event)
            .join(CERNAccessRequestRegForm)
            .filter(RegistrationForm.cern_access_request, CERNAccessRequestRegForm.is_active)
            .all())


def get_registrations(event, regform=None, allow_unpaid=False, only_unpaid=False, requested=False):
    query = Registration.query.with_parent(event)
    if regform:
        query = query.filter(Registration.registration_form_id == regform.id)
    if allow_unpaid:
        query = query.filter(db.or_(Registration.state == RegistrationState.complete,
                             Registration.state == RegistrationState.unpaid))
    elif only_unpaid:
        query = query.filter(Registration.state == RegistrationState.unpaid)
    elif requested:
        query = query.join(CERNAccessRequest).filter(Registration.cern_access_request, CERNAccessRequest.is_active)
    else:
        query = query.filter(Registration.state == RegistrationState.complete)
    return query.all()


def send_adams_post_request(event, registrations, update=False):
    from indico_cern_access.plugin import CERNAccessPlugin
    data = {registration.id: build_access_request_data(registration, event, update=update)
            for registration in registrations}
    headers = {'content-type': 'Application/JSON'}
    json_data = json.dumps([data[key] for key in data])
    r = requests.post(CERNAccessPlugin.settings.get('adams_url'), data=json_data, headers=headers)
    return ((CERNAccessRequestState.accepted, data)
            if r.status_code == requests.codes.ok
            else (CERNAccessRequestState.rejected, data))


def send_adams_delete_request(registrations):
    from indico_cern_access.plugin import CERNAccessPlugin

    data = [generate_access_id(registration.id) for registration in registrations]
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(data)
    r = requests.delete(CERNAccessPlugin.settings.get('adams_url'), data=data, headers=headers)
    return True if r.status_code == requests.codes.ok else False


def generate_access_id(registration_id):
    return 'in{}'.format(registration_id)


def build_access_request_data(registration, event, update=False):
    data = {}
    if update:
        reservation_code = registration.cern_access_request.reservation_code
    else:
        reservation_code = get_random_reservation_code()
    data.update({'$id': generate_access_id(registration.id),
                 '$rc': reservation_code,
                 '$gn': event.title,
                 '$fn': unicode_to_ascii(remove_accents(registration.first_name)),
                 '$ln': unicode_to_ascii(remove_accents(registration.last_name)),
                 '$sd': event.start_dt.strftime('%Y-%m-%dT%H:%M'),
                 '$ed': event.end_dt.strftime('%Y-%m-%dT%H:%M')})
    checksum = ';;'.join('{}:{}'.format(key, value) for key, value in sorted(data.viewitems()))
    signature = hashlib.sha256(checksum).hexdigest()
    data.update({'$si': signature})
    return data


def update_access_request(req):
    event = req.event_new
    existing_forms = get_requested_forms(event)
    requested_forms = req.data['regforms']['regforms']

    existing_forms_ids = {regform.id for regform in existing_forms}
    requested_forms_ids = {regform['regform_id'] for regform in requested_forms}

    allow_unpaid_info = {data['regform_id']: data['allow_unpaid'] for data in requested_forms}

    event_regforms = {regform.id: regform for regform in event.registration_forms}

    # add requests
    for regform_id in requested_forms_ids - existing_forms_ids:
        allow_unpaid = allow_unpaid_info[regform_id]
        regform = event_regforms[regform_id]
        registrations = get_registrations(event, regform=regform, allow_unpaid=allow_unpaid)

        state, data = send_adams_post_request(event, registrations)
        create_access_request_regform(regform, state, allow_unpaid)
        add_access_requests(registrations, data, state)

    # update requests
    for regform_id in set.intersection(requested_forms_ids, existing_forms_ids):
        allow_unpaid = allow_unpaid_info[regform_id]
        regform = event_regforms[regform_id]
        if allow_unpaid != regform.cern_access_request.allow_unpaid:
            if allow_unpaid is True:
                regform.cern_access_request.allow_unpaid = allow_unpaid
                registrations = get_registrations(event, regform=regform, only_unpaid=True)
                state, data = send_adams_post_request(event, registrations)
                add_access_requests(registrations, data, state)
            else:
                regform.cern_access_request.allow_unpaid = allow_unpaid
                registrations = get_registrations(event, regform=regform, only_unpaid=True, requested=True)
                deleted = send_adams_delete_request(registrations)
                if deleted:
                    withdraw_access_requests(registrations)

    # delete requests
    for regform_id in existing_forms_ids - requested_forms_ids:
        regform = event_regforms[regform_id]
        registrations = get_registrations(event, regform=regform, requested=True)
        deleted = send_adams_delete_request(registrations)
        if deleted:
            regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
            withdraw_access_requests(registrations)

    return RequestState.accepted


def add_access_requests(registrations, data, state):
    for registration in registrations:
        create_access_request(registration, state, data[registration.id]["$rc"])


def update_access_requests(registrations, state):
    for access_request in registrations:
        access_request.request_state = state


def withdraw_access_requests(registrations):
    for registration in registrations:
        registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn


def withdraw_event_access_request(req):
    requested_forms = get_requested_forms(req.event_new)
    requested_registrations = get_registrations(req.event_new, requested=True)
    deleted = send_adams_delete_request(requested_registrations)
    if deleted:
        for regform in requested_forms:
            regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        withdraw_access_requests(requested_registrations)


def get_random_reservation_code():
    return 'I' + ''.join(random.sample(string.ascii_uppercase.replace('O', '') + string.digits, 6))


def create_access_request(registration, state, reservation_code):
    if registration.cern_access_request:
        registration.cern_access_request.request_state = state
        registration.cern_access_request.reservation_code = reservation_code
    else:
        registration.cern_access_request = CERNAccessRequest(request_state=state,
                                                             reservation_code=reservation_code)


def create_access_request_regform(regform, state, allow_unpaid):
    if regform.cern_access_request:
        regform.cern_access_request.request_state = state
        regform.cern_access_request.allow_unpaid = allow_unpaid
    else:
        regform.cern_access_request = CERNAccessRequestRegForm(request_state=state,
                                                               allow_unpaid=allow_unpaid)
