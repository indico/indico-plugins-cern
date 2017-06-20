from __future__ import unicode_literals

import json
import random
import string
import requests
import hashlib

from indico.util.string import remove_accents, unicode_to_ascii
from sqlalchemy.orm import joinedload
from indico.core.db import db
from indico.modules.events.requests.models.requests import RequestState
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState

from indico_cern_access.models.access_requests import AccessRequestState, AccessRequest
from indico_cern_access.models.regform_access_requests import RegformAccessRequest


def get_access_request(registartion_id):
    return AccessRequest.query.get(registartion_id)


def get_regforms_with_access_data(event):
    return (RegistrationForm.query
            .with_parent(event)
            .options(joinedload('access_request'))
            .filter(~RegistrationForm.is_deleted)
            .all())


def get_requested_forms(event):
    return (db.session.query(RegformAccessRequest).options(joinedload('registration_form'))
            .filter(RegistrationForm.event_id == event.id)
            .all())


def get_requested_registrations(event):
    return (Registration.query.with_parent(event).options(joinedload('access_request'))
            .filter(~Registration.is_deleted, Registration.access_request)
            .all())


def get_registrations(regform_id, allow_unpaid=False, only_unpaid=False):
    query = Registration.query.filter(Registration.registration_form_id == regform_id, Registration.is_active)
    if allow_unpaid:
        query = query.filter(Registration.state == RegistrationState.complete,
                             Registration.state == RegistrationState.unpaid)
    elif only_unpaid:
        query = query.filter(Registration.state == RegistrationState.unpaid)
    else:
        query = query.filter(Registration.state == RegistrationState.complete)
    return query.all()


def get_requested_accesses(event_id=None, regform_id=None, unpaid_only=False):
    query = db.session.query(AccessRequest).join(Registration)
    if event_id:
        query = query.filter(Registration.event_id == event_id)
    elif regform_id:
        query = query.filter(Registration.registration_form_id == regform_id)
    if unpaid_only:
        query = query.filter(Registration.state == RegistrationState.unpaid)
    return query.all()


def send_adams_post_request(event, registration=None, registrations=None, update=False):
    data = {}
    if registrations:
        for registration in registrations:
            data[registration.id] = parse_post_registration_data(registration, event, update=update)
    elif registration:
        data[registration.id] = parse_post_registration_data(registration, event, update=update)
    headers = {'content-type': 'Application/JSON'}
    json_data = json.dumps([data[key] for key in data])
    print json.loads(json_data)
    from indico_cern_access.plugin import CernAccessPlugin
    r = requests.post(CernAccessPlugin.settings.get('adams_url'), data=json_data, headers=headers)
    if r.status_code == requests.codes.ok:
        return AccessRequestState.accepted, data
    else:
        return AccessRequestState.rejected, data


def send_adams_delete_request(access_requests=None, registration=None):
    data = []
    if access_requests:
        for request in access_requests:
            data.append(parse_delete_registration_data(request.registration))
    elif registration:
        data.append(parse_delete_registration_data(registration))
    headers = {'content-type': 'Application/JSON'}
    data = json.dumps(data)
    from indico_cern_access.plugin import CernAccessPlugin
    r = requests.delete(CernAccessPlugin.settings.get('adams_url'), data=data, headers=headers)
    if r.status_code == requests.codes.ok:
        return True
    else:
        return False


def parse_delete_registration_data(registration):
    from indico_cern_access.plugin import CernAccessPlugin
    return CernAccessPlugin.settings.get('id_prefix') + '%d' % registration.id


def parse_post_registration_data(registration, event, update=False):
    from indico_cern_access.plugin import CernAccessPlugin
    data = {}
    if update:
        reservation_code = registration.access_request.reservation_code
    else:
        reservation_code = get_random_reservation_code()
    data.update({'$id': CernAccessPlugin.settings.get('id_prefix') + '%d' % registration.id,
                 '$rc': reservation_code,
                 '$fn': unicode_to_ascii(remove_accents(registration.first_name)),
                 '$ln': unicode_to_ascii(remove_accents(registration.last_name)),
                 '$sd': event.start_dt.strftime('%Y-%m-%dT%H:%M'),
                 '$ed': event.end_dt.strftime('%Y-%m-%dT%H:%M'),
                 })
    checksum = ''
    sortedkeys = sorted(data.keys())
    for i, key in enumerate(sortedkeys):
        if i == (len(sortedkeys)-1):
            checksum += '%s:%s' % (key, data[key])
        else:
            checksum += '%s:%s;;' % (key, data[key])
    signature = hashlib.sha256().hexdigest()
    data.update({'$si': signature})
    return data


def update_access_request(req):
    already_requested = get_requested_forms(req.event_new)
    just_requested = req.data['regforms']['regforms']

    # add and update forms
    for regform in just_requested:
        allow_unpaid = bool(regform['allow_unpaid'])
        regform_id = regform['regform_id']
        already_requested_form = next((form for form in already_requested if form.form_id == regform_id), None)
        if already_requested_form is None:
            registrations = get_registrations(regform_id, allow_unpaid=allow_unpaid)

            state, data = send_adams_post_request(req.event_new, registrations=registrations)
            new_form = RegformAccessRequest(form_id=regform_id,
                                            request_state=state,
                                            allow_unpaid=allow_unpaid)
            db.session.add(new_form)
            add_registrations(data, state)

        elif allow_unpaid != already_requested_form.allow_unpaid:
            already_requested_form.allow_unpaid = allow_unpaid
            if allow_unpaid is True:
                registrations = get_registrations(regform_id, only_unpaid=True)
                state, data = send_adams_post_request(req.event_new, registrations=registrations)
                add_registrations(data, state)
            else:
                access_requests = get_requested_accesses(regform_id=regform_id, unpaid_only=True)
                deleted = send_adams_delete_request(access_requests=access_requests)
                if deleted:
                    delete_registrations(access_requests)

    # disable forms
    for regform in already_requested:
        just_requested_form = next((form for form in just_requested if form['regform_id'] == regform.form_id), None)
        if just_requested_form is None:
            access_requests = get_requested_accesses(regform_id=regform.form_id)
            deleted = send_adams_delete_request(access_requests=access_requests)
            if deleted:
                db.session.delete(regform)
                delete_registrations(access_requests)
    db.session.flush()
    return RequestState.accepted


def add_registrations(registrations, state):
    access_requests = []
    for key in registrations:
            access_request = AccessRequest(registration_id=key,
                                           request_state=state,
                                           reservation_code=registrations[key]["$rc"])
            access_requests.append(access_request)
    db.session.add_all(access_requests)


def update_registrations(registrations, state):
    for access_request in registrations:
        access_request.state = state
    db.session.flush()


def delete_registrations(access_requests):
    for request in access_requests:
            db.session.delete(request)


def withdraw_access_request(req):
    requested_forms = get_requested_forms(req.event_new)
    requested_accesses = get_requested_accesses(event_id=req.event_new.id)
    send_adams_delete_request(access_requests=requested_accesses)
    for regform in requested_forms:
        db.session.delete(regform)
    for requested_access in requested_accesses:
        db.session.delete(requested_access)
    db.session.flush()


def get_random_reservation_code():
    return 'I'.join(random.choice(string.ascii_uppercase.replace('O', '') + string.digits) for _ in range(6))
