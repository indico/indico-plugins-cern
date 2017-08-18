from __future__ import unicode_literals

import hashlib
import hmac
import json
import random
import string

import requests
from flask import session
from pytz import timezone

from indico.core.db import db
from indico.core.errors import IndicoError
from indico.core.notifications import make_email, send_email
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events.registration.controllers.management.tickets import generate_ticket
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.modules.events.requests.exceptions import RequestModuleError
from indico.modules.events.requests.models.requests import RequestState
from indico.util.string import remove_accents, unicode_to_ascii
from indico.web.flask.templating import get_template_module

from indico_cern_access.models.access_request_regforms import CERNAccessRequestRegForm
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState


def get_requested_forms(event):
    """Returns list of registration forms with requested access to CERN"""
    return (RegistrationForm.query.with_parent(event)
            .join(CERNAccessRequestRegForm)
            .filter(CERNAccessRequestRegForm.is_active)
            .all())


def get_event_registrations(event, regform=None, allow_unpaid=False, only_unpaid=False, requested=False):
    """By default returns a list of complete registrations of an event

    :param regform: if specified, returns only registrations with that registration form
    :param allow_unpaid: if True, returns not only complete registrations but also unpaid ones
    :param only_unpaid: if True, returns only unpaid registrations
    :param requested: if True, returns registrations with requested access to CERN
    """
    query = Registration.query.with_parent(event).filter(Registration.is_active)
    if regform:
        query = query.filter(Registration.registration_form_id == regform.id)
    if allow_unpaid:
        query = query.filter(db.or_(Registration.state == RegistrationState.complete,
                             Registration.state == RegistrationState.unpaid))
    elif only_unpaid:
        query = query.filter(Registration.state == RegistrationState.unpaid)
    elif requested:
        query = query.join(CERNAccessRequest).filter(CERNAccessRequest.is_active)
    else:
        query = query.filter(Registration.state == RegistrationState.complete)
    return query.all()


def send_adams_post_request(event, registrations, update=False):
    """ Sends POST request to ADaMS API

    :param update: if True, send request updating already stored data
    """
    from indico_cern_access.plugin import CERNAccessPlugin
    data = {registration.id: build_access_request_data(registration, event, update=update)
            for registration in registrations}
    headers = {'content-type': 'Application/JSON'}
    auth = (CERNAccessPlugin.settings.get('login'), CERNAccessPlugin.settings.get('password'))
    json_data = json.dumps([data[key] for key in data])
    r = requests.post(CERNAccessPlugin.settings.get('adams_url'), data=json_data, headers=headers, auth=auth)
    return ((CERNAccessRequestState.accepted, data)
            if r.status_code == requests.codes.ok
            else (CERNAccessRequestState.rejected, data))


def send_adams_delete_request(registrations):
    """Sends DELETE request to ADaMS API"""
    from indico_cern_access.plugin import CERNAccessPlugin

    data = [generate_access_id(registration.id) for registration in registrations]
    headers = {'Content-Type': 'application/json'}
    auth = (CERNAccessPlugin.settings.get('login'), CERNAccessPlugin.settings.get('password'))
    data = json.dumps(data)
    r = requests.delete(CERNAccessPlugin.settings.get('adams_url'), data=data, headers=headers, auth=auth)
    return True if r.status_code == requests.codes.ok else False


def generate_access_id(registration_id):
    """Generates an id in format required by ADaMS API"""
    return 'in{}'.format(registration_id)


def build_access_request_data(registration, event, update=False):
    """Returns a dictionary with data required by ADaMS API"""
    from indico_cern_access.plugin import CERNAccessPlugin

    tz = timezone('Europe/Zurich')
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
                 '$sd': event.start_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M'),
                 '$ed': event.end_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M')})
    checksum = ';;'.join('{}:{}'.format(key, value) for key, value in sorted(data.viewitems()))
    signature = hmac.new(str(CERNAccessPlugin.settings.get('secret_key')), checksum, hashlib.sha256)
    data.update({'$si': signature.hexdigest()})
    return data


def update_access_request(req):
    """Adds, upodates and deletes CERN access requests from registration forms"""
    event = req.event_new
    existing_forms = get_requested_forms(event)
    requested_forms = req.data['regforms']['regforms']

    # pull out ids of existing and requested forms to easily check which ones should be added/deleted/updated afterwards
    existing_forms_ids = {regform.id for regform in existing_forms}
    requested_forms_ids = {regform['regform_id'] for regform in requested_forms}

    allow_unpaid_info = {data['regform_id']: data['allow_unpaid'] for data in requested_forms}

    event_regforms = {regform.id: regform for regform in event.registration_forms}

    # add requests
    for regform_id in requested_forms_ids - existing_forms_ids:
        allow_unpaid = allow_unpaid_info[regform_id]
        regform = event_regforms[regform_id]
        registrations = get_event_registrations(event, regform=regform, allow_unpaid=allow_unpaid)
        state, data = send_adams_post_request(event, registrations)
        if state == CERNAccessRequestState.accepted:
            create_access_request_regform(regform, state, allow_unpaid)
            enable_ticketing(regform)
            add_access_requests(registrations, data, state)
            if regform.ticket_on_email:
                send_tickets(registrations)
        else:
            raise RequestModuleError()

    # update requests
    for regform_id in set.intersection(requested_forms_ids, existing_forms_ids):
        allow_unpaid = allow_unpaid_info[regform_id]
        regform = event_regforms[regform_id]
        if allow_unpaid != regform.cern_access_request.allow_unpaid:
            if allow_unpaid is True:
                registrations = get_event_registrations(event, regform=regform, only_unpaid=True)
                state, data = send_adams_post_request(event, registrations)
                if state == CERNAccessRequestState.accepted:
                    regform.cern_access_request.allow_unpaid = allow_unpaid
                    add_access_requests(registrations, data, state)
                    if regform.ticket_on_email:
                        send_tickets(registrations)
                else:
                    raise RequestModuleError()
            else:
                registrations = get_event_registrations(event, regform=regform, only_unpaid=True, requested=True)
                deleted = send_adams_delete_request(registrations)
                if deleted:
                    regform.cern_access_request.allow_unpaid = allow_unpaid
                    withdraw_access_requests(registrations)
                    notify_access_withdrawn(registrations)
                else:
                    raise RequestModuleError()

    # delete requests
    for regform_id in existing_forms_ids - requested_forms_ids:
        regform = event_regforms[regform_id]
        registrations = get_event_registrations(event, regform=regform, requested=True)
        deleted = send_adams_delete_request(registrations)
        if deleted:
            regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
            withdraw_access_requests(registrations)
            notify_access_withdrawn(registrations)
        else:
            raise RequestModuleError()


def add_access_requests(registrations, data, state):
    """Adds CERN access requests for registrations"""
    for registration in registrations:
        create_access_request(registration, state, data[registration.id]["$rc"])


def update_access_requests(registrations, state):
    """Updates already requested registrations"""
    for registration in registrations:
        registration.cern_access_request.request_state = state


def withdraw_access_requests(registrations):
    """Withdraws CERN access requests for registrations"""
    for registration in registrations:
        registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn


def withdraw_event_access_request(req):
    """Withdraws all CERN access requests of an event"""
    from indico_cern_access.plugin import CERNAccessPlugin
    requested_forms = get_requested_forms(req.event_new)
    requested_registrations = get_event_registrations(req.event_new, requested=True)
    deleted = send_adams_delete_request(requested_registrations)
    if deleted:
        access_tpl = DesignerTemplate.get_one(CERNAccessPlugin.settings.get('access_ticket_template_id'))
        for regform in requested_forms:
            regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
            if regform.ticket_template == access_tpl:
                regform.ticket_template = None
        withdraw_access_requests(requested_registrations)
        notify_access_withdrawn(requested_registrations)
    else:
        raise RequestModuleError()


def get_random_reservation_code():
    """Generates random reservation code for data required by ADaMS API"""
    return 'I' + ''.join(random.sample(string.ascii_uppercase.replace('O', '') + string.digits, 6))


def create_access_request(registration, state, reservation_code):
    """Creates CERN access request object for registration"""
    if registration.cern_access_request:
        registration.cern_access_request.request_state = state
        registration.cern_access_request.reservation_code = reservation_code
    else:
        registration.cern_access_request = CERNAccessRequest(request_state=state,
                                                             reservation_code=reservation_code)


def create_access_request_regform(regform, state, allow_unpaid):
    """Creates CERN access request object for registration form"""
    if regform.cern_access_request:
        regform.cern_access_request.request_state = state
        regform.cern_access_request.allow_unpaid = allow_unpaid
    else:
        regform.cern_access_request = CERNAccessRequestRegForm(request_state=state,
                                                               allow_unpaid=allow_unpaid)


def is_authorized_user(user):
    """Checks if user is authorized to request access to CERN"""
    from indico_cern_access.plugin import CERNAccessPlugin
    return CERNAccessPlugin.settings.acls.contains_user('authorized_users', user)


def notify_access_withdrawn(registrations):
    """Notifies participants when access to CERN has been withdrawn"""
    for registration in registrations:
        template = get_template_module('cern_access:request_withdrawn_email.html', registration=registration)
        from_address = registration.registration_form.sender_address
        email = make_email(to_list=registration.email, from_address=from_address,
                           template=template, html=True)
        send_email(email, event=registration.registration_form.event_new, module='Registration', user=session.user)


def send_tickets(registrations):
    """Sends tickets to access CERN site to registered users"""
    for registration in registrations:
        template = get_template_module('cern_access:ticket_email.html', registration=registration)
        from_address = registration.registration_form.sender_address
        attachments = [{
            'name': 'Ticket.pdf',
            'binary': generate_ticket(registration).getvalue()
        }]
        email = make_email(to_list=registration.email, from_address=from_address,
                           template=template, html=True, attachments=attachments)
        send_email(email, event=registration.registration_form.event_new, module='Registration',
                   user=session.user)


def enable_ticketing(regform):
    """Enables ticketing module automatically"""
    if not regform.tickets_enabled:
        regform.tickets_enabled = True
        regform.tickets_on_email = True
        regform.ticket_on_event_page = True
        regform.ticket_on_summary_page = True
