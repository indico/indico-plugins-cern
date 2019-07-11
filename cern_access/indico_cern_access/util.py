# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import hashlib
import hmac
import json
import random
import re

import dateutil.parser
import requests
from flask import session
from jinja2.filters import do_truncate
from pytz import timezone
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.notifications import make_email, send_email
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import get_ticket_attachments
from indico.modules.events.requests.models.requests import Request
from indico.util.date_time import now_utc
from indico.util.placeholders import replace_placeholders
from indico.util.string import remove_accents, unicode_to_ascii
from indico.web.flask.templating import get_template_module

from indico_cern_access import _
from indico_cern_access.models.access_request_regforms import CERNAccessRequestRegForm
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState


def get_last_request(event):
    """Return the last CERN Access request for the event."""
    from indico_cern_access.definition import CERNAccessRequestDefinition
    return Request.find_latest_for_event(event, CERNAccessRequestDefinition.name)


def get_requested_forms(event):
    """Return list of registration forms with requested access to CERN."""
    return (RegistrationForm.query.with_parent(event)
            .join(CERNAccessRequestRegForm)
            .filter(CERNAccessRequestRegForm.is_active)
            .all())


def get_requested_registrations(event, regform=None, only_active=False):
    """By default returns a list of requested registrations of an event

    :param regform: if specified, returns only registrations with that registration form
    """
    query = (Registration.query.with_parent(event)
             .join(CERNAccessRequest))

    if only_active:
        query = query.filter(CERNAccessRequest.is_active)
    else:
        query = query.filter(~CERNAccessRequest.is_withdrawn)

    if regform:
        query = query.filter(Registration.registration_form_id == regform.id)
    return query.all()


def _send_adams_http_request(method, data):
    from indico_cern_access.plugin import CERNAccessPlugin

    url = CERNAccessPlugin.settings.get('adams_url')
    credentials = (CERNAccessPlugin.settings.get('username'), CERNAccessPlugin.settings.get('password'))
    request_headers = {'Content-Type': 'application/json'}

    try:
        r = requests.request(method, url, data=json.dumps(data), headers=request_headers, auth=credentials)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        CERNAccessPlugin.logger.exception('Request to ADAMS failed (%r)', data)
        raise AdamsError(_('Sending request to ADAMS failed'))
    return r.status_code == requests.codes.all_ok


def send_adams_post_request(event, registrations, update=False):
    """Send POST request to ADaMS API

    :param update: if True, send request updating already stored data
    """
    data = {reg.id: build_access_request_data(reg, event, generate_code=(not update)) for reg in registrations}
    _send_adams_http_request('POST', data.values())
    return CERNAccessRequestState.active, data


def send_adams_delete_request(registrations):
    """Send DELETE request to ADaMS API."""
    data = [generate_access_id(registration.id) for registration in registrations]
    _send_adams_http_request('DELETE', data)


def generate_access_id(registration_id):
    """Generate an id in format required by ADaMS API."""
    return 'in{}'.format(registration_id)


def build_access_request_data(registration, event, generate_code):
    """Return a dictionary with data required by ADaMS API."""
    from indico_cern_access.plugin import CERNAccessPlugin
    start_dt, end_dt = get_access_dates(get_last_request(event))
    tz = timezone('Europe/Zurich')
    title = do_truncate(None, unicode_to_ascii(remove_accents(event.title)), 100, leeway=0)
    if generate_code:
        reservation_code = get_random_reservation_code()
    else:
        reservation_code = registration.cern_access_request.reservation_code
    data = {'$id': generate_access_id(registration.id),
            '$rc': reservation_code,
            '$gn': title,
            '$fn': unicode_to_ascii(remove_accents(registration.first_name)),
            '$ln': unicode_to_ascii(remove_accents(registration.last_name)),
            '$sd': start_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M'),
            '$ed': end_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M')}

    if registration.cern_access_request and registration.cern_access_request.license_plate:
        data['$lp'] = registration.cern_access_request.license_plate

    checksum = ';;'.join('{}:{}'.format(key, value) for key, value in sorted(data.viewitems()))
    signature = hmac.new(str(CERNAccessPlugin.settings.get('secret_key')), checksum, hashlib.sha256)
    data['$si'] = signature.hexdigest()
    return data


def handle_event_time_update(event):
    """Update access requests after an event time change"""
    registrations = get_requested_registrations(event=event, only_active=True)
    if registrations:
        state = send_adams_post_request(event, registrations, update=True)[0]
        if state == CERNAccessRequestState.active:
            update_access_requests(registrations, state)


def update_access_request(req):
    """Add, update and delete CERN access requests from registration forms."""

    event = req.event
    existing_forms = get_requested_forms(event)
    requested_forms = req.data['regforms']

    # Pull out ids of existing and requested forms to easily
    # check which ones should be added/deleted afterwards
    existing_forms_ids = {regform.id for regform in existing_forms}
    requested_forms_ids = {int(id) for id in requested_forms}
    event_regforms = {regform.id: regform for regform in event.registration_forms}

    # add requests
    for regform_id in requested_forms_ids - existing_forms_ids:
        regform = event_regforms[regform_id]
        create_access_request_regform(regform, state=CERNAccessRequestState.active)
        enable_ticketing(regform)

    # delete requests
    for regform_id in existing_forms_ids - requested_forms_ids:
        regform = event_regforms[regform_id]
        registrations = get_requested_registrations(event, regform=regform)
        if registrations:
            send_adams_delete_request(registrations)
        regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        remove_access_template(regform)
        withdraw_access_requests(registrations)
        notify_access_withdrawn(registrations)


def remove_access_template(regform):
    from indico_cern_access.plugin import CERNAccessPlugin
    access_tpl = CERNAccessPlugin.settings.get('access_ticket_template')
    if regform.ticket_template == access_tpl:
        regform.ticket_template = None


def add_access_requests(registrations, data, state):
    """Add CERN access requests for registrations."""
    for registration in registrations:
        create_access_request(registration, state, data[registration.id]['$rc'])


def update_access_requests(registrations, state):
    """Update already requested registrations."""
    for registration in registrations:
        registration.cern_access_request.request_state = state


def withdraw_access_requests(registrations):
    """Withdraw CERN access requests for registrations."""
    for registration in registrations:
        registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        registration.cern_access_request.clear_identity_data()


def withdraw_event_access_request(req):
    """Withdraw all CERN access requests of an event."""
    requested_forms = get_requested_forms(req.event)
    requested_registrations = get_requested_registrations(req.event)
    if requested_registrations:
        send_adams_delete_request(requested_registrations)
    for regform in requested_forms:
        regform.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        remove_access_template(regform)
    withdraw_access_requests(requested_registrations)
    notify_access_withdrawn(requested_registrations)


def get_random_reservation_code():
    """Generate random reservation code for data required by ADaMS API."""
    charset = 'ABCDEFGHIJKLMNPQRSTUVWXYZ123456789'
    return 'I' + ''.join(random.sample(charset, 6))


def create_access_request(registration, state, reservation_code):
    """Create CERN access request object for registration."""
    if registration.cern_access_request:
        registration.cern_access_request.request_state = state
        registration.cern_access_request.reservation_code = reservation_code
    else:
        registration.cern_access_request = CERNAccessRequest(request_state=state,
                                                             reservation_code=reservation_code)


def create_access_request_regform(regform, state):
    """Create CERN access request object for registration form."""
    from indico_cern_access.plugin import CERNAccessPlugin
    access_tpl = CERNAccessPlugin.settings.get('access_ticket_template')
    if state == CERNAccessRequestState.active and access_tpl:
        regform.ticket_template = access_tpl
    if regform.cern_access_request:
        regform.cern_access_request.request_state = state
    else:
        regform.cern_access_request = CERNAccessRequestRegForm(request_state=state)


def is_authorized_user(user):
    """Check if user is authorized to request access to CERN."""
    from indico_cern_access.plugin import CERNAccessPlugin
    if user.is_admin:
        return True
    return CERNAccessPlugin.settings.acls.contains_user('authorized_users', user)


def notify_access_withdrawn(registrations):
    """Notify participants when access to CERN has been withdrawn."""
    for registration in registrations:
        template = get_template_module('cern_access:emails/request_withdrawn_email.html', registration=registration)
        email = make_email(to_list=registration.email, template=template, html=True)
        send_email(email, event=registration.registration_form.event, module='Registration',
                   user=(session.user if session else None))


def send_ticket(registration):
    """Send the ticket to access the CERN site by email."""
    start_dt, end_dt = get_access_dates(get_last_request(registration.event))
    template = get_template_module('cern_access:emails/ticket_email.html', registration=registration,
                                   start_dt=start_dt, end_dt=end_dt)
    attachments = get_ticket_attachments(registration)
    email = make_email(to_list=registration.email, template=template, html=True, attachments=attachments)
    send_email(email, event=registration.registration_form.event, module='Registration', user=session.user)


def enable_ticketing(regform):
    """Enable ticketing module automatically."""
    if not regform.tickets_enabled:
        regform.tickets_enabled = True
        regform.ticket_on_email = True
        regform.ticket_on_event_page = True
        regform.ticket_on_summary_page = True


def is_category_blacklisted(category):
    from indico_cern_access.plugin import CERNAccessPlugin
    return any(category.id == int(cat['id']) for cat in CERNAccessPlugin.settings.get('excluded_categories'))


def is_event_too_early(event):
    from indico_cern_access.plugin import CERNAccessPlugin
    earliest_start_dt = CERNAccessPlugin.settings.get('earliest_start_dt')
    return earliest_start_dt is not None and event.start_dt < earliest_start_dt


def grant_access(registrations, regform, email_subject=None, email_body=None, email_sender=None):
    event = regform.event
    new_registrations = [reg for reg in registrations
                         if not (reg.cern_access_request and
                                 not reg.cern_access_request.is_withdrawn and
                                 reg.cern_access_request.request_state == CERNAccessRequestState.active)]
    state, data = send_adams_post_request(event, new_registrations)
    add_access_requests(new_registrations, data, state)
    registrations_without_data = []
    for registration in new_registrations:
        if not registration.cern_access_request.has_identity_info:
            registrations_without_data.append(registration)
        elif regform.ticket_on_email:
            send_ticket(registration)

    if registrations_without_data:
        send_form_link(registrations_without_data, email_subject, email_body, email_sender)


def send_form_link(registrations, email_subject_tpl, email_body_tpl, email_sender):
    """Send a mail asking for personal information to be filled in using a web form."""
    for registration in registrations:
        email_body = replace_placeholders('cern-access-email', email_body_tpl,
                                          regform=registration.registration_form, registration=registration)
        email_subject = replace_placeholders('cern-access-email', email_subject_tpl,
                                             regform=registration.registration_form, registration=registration)
        template = get_template_module('cern_access:emails/identity_data_form_email.html', registration=registration,
                                       email_subject=email_subject, email_body=email_body)
        email = make_email(to_list=registration.email, from_address=email_sender, template=template, html=True)
        send_email(email, event=registration.registration_form.event, module='Registration', user=session.user)


def revoke_access(registrations):
    if not registrations:
        return
    send_adams_delete_request(registrations)
    requested_registrations = [reg for reg in registrations if
                               reg.cern_access_request and not
                               reg.cern_access_request.is_withdrawn and
                               reg.cern_access_request.request_state == CERNAccessRequestState.active]
    withdraw_access_requests(requested_registrations)
    notify_access_withdrawn(requested_registrations)


def check_access(req):
    user_authorized = is_authorized_user(session.user)
    category_blacklisted = is_category_blacklisted(req.event.category)
    too_early = is_event_too_early(req.event)
    if not user_authorized or category_blacklisted or too_early:
        raise Forbidden()


def get_access_dates(req):
    start_dt_override = req.data['start_dt_override']
    end_dt_override = req.data['end_dt_override']
    if start_dt_override and end_dt_override:
        start_dt_override = dateutil.parser.parse(start_dt_override)
        end_dt_override = dateutil.parser.parse(end_dt_override)
        return start_dt_override, end_dt_override
    else:
        return req.event.start_dt, req.event.end_dt


def sanitize_personal_data():
    from indico_cern_access.plugin import CERNAccessPlugin
    query = (CERNAccessRequest.query
             .join(CERNAccessRequest.registration)
             .join(Registration.event)
             .filter(CERNAccessRequest.has_identity_info,
                     Event.end_dt < now_utc() - CERNAccessPlugin.settings.get('delete_personal_data_after')))
    for req in query:
        req.clear_identity_data()
        CERNAccessPlugin.logger.info('Removing personal data for registrant %d', req.registration_id)
    db.session.flush()


def sanitize_license_plate(number):
    """Sanitize a license plate number to [A-Z0-9]+, no dashes/spaces."""
    number = re.sub(r'[ -]', '', number.upper())
    return number if re.match(r'^[A-Z0-9]+$', number) else None


class AdamsError(Exception):
    pass
