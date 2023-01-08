# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from datetime import time, timedelta

from flask import g, request, session
from flask_pluginengine import render_plugin_template
from werkzeug.exceptions import Forbidden
from wtforms.fields import StringField, URLField
from wtforms.validators import DataRequired, Optional
from wtforms_sqlalchemy.fields import QuerySelectField

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import DatetimeConverter, ModelConverter, TimedeltaConverter
from indico.modules.designer import TemplateType
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events import Event
from indico.modules.events.registration.controllers.display import RHRegistrationForm
from indico.modules.events.registration.forms import TicketsForm
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.placeholders.registrations import (EventTitlePlaceholder, FirstNamePlaceholder,
                                                                           LastNamePlaceholder)
from indico.modules.events.registration.util import RegistrationSchemaBase
from indico.modules.events.registration.views import (WPDisplayRegistrationFormConference,
                                                      WPDisplayRegistrationFormSimpleEvent)
from indico.util.countries import get_countries
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import (IndicoDateTimeField, IndicoPasswordField, MultipleItemsField, PrincipalListField,
                                     TimeDeltaField)

from indico_cern_access import _
from indico_cern_access.blueprint import blueprint
from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState
from indico_cern_access.placeholders import (AccessPeriodPlaceholder, FormLinkPlaceholder, TicketAccessDatesPlaceholder,
                                             TicketLicensePlatePlaceholder)
from indico_cern_access.schemas import RequestAccessSchema
from indico_cern_access.util import (build_access_request_data, get_access_dates, get_last_request, get_requested_forms,
                                     get_requested_registrations, handle_event_time_update, notify_access_withdrawn,
                                     send_adams_delete_request, send_adams_post_request, update_access_requests,
                                     withdraw_access_requests)
from indico_cern_access.views import WPAccessRequestDetails


class PluginSettingsForm(IndicoForm):
    adams_url = URLField(_('ADaMS URL'), [DataRequired()],
                         description=_('The URL of the ADaMS REST API'))
    username = StringField(_('Username'), [DataRequired()],
                           description=_('The login used to authenticate with ADaMS service'))
    password = IndicoPasswordField(_('Password'), [DataRequired()],
                                   description=_('The password used to authenticate with ADaMS service'))
    authorized_users = PrincipalListField(_('Authorized users'), allow_groups=True,
                                          description=_('List of users/groups who can send requests'))
    excluded_categories = MultipleItemsField('Excluded categories', fields=[{'id': 'id', 'caption': 'Category ID'}])
    access_ticket_template = QuerySelectField(_("Access ticket template"), allow_blank=True,
                                              blank_text=_("No access ticket selected"), get_label='title',
                                              description=_("Ticket template allowing access to CERN"))
    earliest_start_dt = IndicoDateTimeField(_("Earliest start date"), [Optional()], default_time=time(0, 0),
                                            description=_("The earliest date an event can start to qualify for CERN "
                                                          "access badges"))
    delete_personal_data_after = TimeDeltaField(_('Delete personal data'), [DataRequired()], units=('days',),
                                                description=_('Personal data will be deleted once the event has '
                                                              'finished and the duration specified here has been '
                                                              'exceeded. Once the data has been deleted, access badges '
                                                              'will not be accessible anymore.'))
    api_username = StringField(_('Username'), [DataRequired()], description=_('The username to access the API'))
    api_password = IndicoPasswordField(_('Password'), [DataRequired()], toggle=True,
                                       description=_('The password to access the API'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_ticket_template.query = (DesignerTemplate.query
                                             .filter(DesignerTemplate.category_id == 0,
                                                     DesignerTemplate.type == TemplateType.badge)
                                             .order_by(db.func.lower(DesignerTemplate.title)))


class CERNAccessPlugin(IndicoPlugin):
    """CERN Access Request

    Provides a service request through which event managers can ask for
    access to the CERN site for the participants of the event
    """

    settings_form = PluginSettingsForm
    configurable = True
    default_settings = {
        'adams_url': '',
        'username': '',
        'password': '',
        'excluded_categories': [],
        'access_ticket_template': None,
        'earliest_start_dt': None,
        'delete_personal_data_after': timedelta(days=180),
        'api_username': '',
        'api_password': '',
    }
    settings_converters = {
        'access_ticket_template': ModelConverter(DesignerTemplate),
        'earliest_start_dt': DatetimeConverter,
        'delete_personal_data_after': TimedeltaConverter,
    }
    acl_settings = {'authorized_users'}
    default_event_settings = {
        'email_subject': None,
        'email_body': None,
    }

    def init(self):
        super().init()
        self.template_hook('registration-status-flag', self._get_access_status)
        self.template_hook('registration-status-action-button', self._get_access_action_button)
        self.template_hook('regform-container-attrs', self._get_regform_container_attrs, markup=False)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.event.registration_deleted, self._registration_deleted)
        self.connect(signals.event.registration_created, self._registration_created)
        self.connect(signals.event.timetable.times_changed, self._event_time_changed, sender=Event)
        self.connect(signals.event.registration_personal_data_modified, self._registration_modified)
        self.connect(signals.event.registration_form_deleted, self._registration_form_deleted)
        self.connect(signals.event.deleted, self._event_deleted)
        self.connect(signals.event.updated, self._event_title_changed)
        self.connect(signals.event.is_ticketing_handled, self._is_ticketing_handled)
        self.connect(signals.event.is_ticket_blocked, self._is_ticket_blocked)
        self.connect(signals.core.form_validated, self._form_validated)
        self.connect(signals.event.designer.print_badge_template, self._print_badge_template)
        self.connect(signals.event.registration.generate_ticket_qr_code, self._generate_ticket_qr_code)
        self.connect(signals.core.get_placeholders, self._get_designer_placeholders, sender='designer-fields')
        self.connect(signals.core.get_placeholders, self._get_email_placeholders, sender='cern-access-email')
        self.connect(signals.plugin.schema_pre_load, self._registration_schema_pre_load)
        self.inject_bundle('main.js', WPDisplayRegistrationFormConference)
        self.inject_bundle('main.js', WPDisplayRegistrationFormSimpleEvent)
        self.inject_bundle('main.css', WPDisplayRegistrationFormConference)
        self.inject_bundle('main.css', WPDisplayRegistrationFormSimpleEvent)
        self.inject_bundle('main.css', WPAccessRequestDetails)

    def _registration_schema_pre_load(self, schema, data, **kwargs):
        if not issubclass(schema, RegistrationSchemaBase):
            return
        if type(g.rh) is not RHRegistrationForm:
            return
        regform = g.rh.regform
        if not regform.cern_access_request or not regform.cern_access_request.is_active:
            return
        req = get_last_request(regform.event)
        if not req or not req.data['during_registration']:
            return
        cern_access_data = {k: data.pop(k) for k in list(data) if k.startswith('cern_access_')}
        if req.data['during_registration_required']:
            cern_access_data['cern_access_request_cern_access'] = True
        g.cern_access_request_data = RequestAccessSchema().load(cern_access_data)

    def _get_regform_container_attrs(self, event, regform, management, registration=None, **kwargs):
        if management or registration is not None:
            return
        if not regform.cern_access_request or not regform.cern_access_request.is_active:
            return
        req = get_last_request(event)
        if not req.data['during_registration']:
            return
        required = req.data['during_registration_required']
        preselected = req.data['during_registration_preselected'] and not required
        start_dt, end_dt = get_access_dates(req)
        return {
            'data-cern-access': json.dumps({
                'countries': get_countries(),
                'start': start_dt.astimezone(event.tzinfo).isoformat(),
                'end': end_dt.astimezone(event.tzinfo).isoformat(),
                'required': required,
                'preselected': preselected,
            })
        }

    def get_blueprints(self):
        return blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return CERNAccessRequestDefinition

    def _get_access_action_button(self, regform, **kwargs):
        if regform.cern_access_request and regform.cern_access_request.is_active:
            return render_plugin_template('cern_access_action_button.html', regform=regform)

    def _get_access_status(self, regform, registration, header, **kwargs):
        if regform.cern_access_request and regform.cern_access_request.is_active:
            return render_plugin_template('cern_access_status.html',
                                          registration=registration,
                                          header=header)

    def _is_past_event(self, event):
        end_dt = get_access_dates(get_last_request(event))[1]
        return end_dt < now_utc()

    def _registration_deleted(self, registration, permanent=False, **kwargs):
        """Withdraw CERN access request for deleted registrations."""
        if not (access_request := registration.cern_access_request):
            return
        if not self._is_past_event(registration.event):
            if access_request.is_active:
                send_adams_delete_request([registration])
            access_request.request_state = CERNAccessRequestState.withdrawn
        if permanent and access_request.has_identity_info:
            # archive registration data and detach request
            self.logger.info('Archiving request %r', access_request)
            access_request.archive()

    def _registration_created(self, registration, management, **kwargs):
        if management:
            return

        regform = registration.registration_form
        access_request_data = g.pop('cern_access_request_data', None)

        if not regform.cern_access_request or not regform.cern_access_request.is_active or not access_request_data:
            return

        req = get_last_request(registration.event)
        if not req or not req.data['during_registration']:
            return

        required = req.data['during_registration_required']
        if not required and not access_request_data['request_cern_access']:
            return

        registration.cern_access_request = CERNAccessRequest(birth_date=access_request_data['birth_date'],
                                                             nationality=access_request_data['nationality'],
                                                             birth_place=access_request_data['birth_place'],
                                                             license_plate=access_request_data['license_plate'],
                                                             request_state=CERNAccessRequestState.not_requested,
                                                             reservation_code='')

    def _event_time_changed(self, sender, obj, **kwargs):
        """Update event time in CERN access requests in ADaMS."""
        handle_event_time_update(obj)

    def _registration_form_deleted(self, registration_form, **kwargs):
        """
        Withdraw CERN access request for deleted registration form and
        corresponding registrations.
        """
        if (registration_form.cern_access_request and registration_form.cern_access_request.is_active and
                not self._is_past_event(registration_form.event)):
            requests = get_requested_registrations(registration_form.event, regform=registration_form)
            if requests:
                # Notify ADAMS about only requests that it knows about (active)
                active_requests = [r for r in requests if r.is_active]
                send_adams_delete_request(active_requests)
                # Withdraw all requests
                withdraw_access_requests(requests)
                # Notify users who have already got a badge
                notify_access_withdrawn(active_requests)
            registration_form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_deleted(self, event, **kwargs):
        """
        Withdraw CERN access request for registration forms and corresponding
        registrations of deleted event.
        """
        access_requests_forms = get_requested_forms(event)
        if access_requests_forms and not self._is_past_event(event):
            requests = get_requested_registrations(event=event)
            if requests:
                # Notify ADAMS about only requests that it knows about (active)
                active_requests = [r for r in requests if r.is_active]
                send_adams_delete_request(active_requests)
                # Withdraw all requests
                withdraw_access_requests(requests)
                # Notify users who have already got a badge
                notify_access_withdrawn(active_requests)
            for form in access_requests_forms:
                form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_modified(self, registration, change, **kwargs):
        """If name of registration changed, updates the ADaMS CERN access request."""
        access_request = registration.cern_access_request
        if access_request and access_request.is_active and ('first_name' in change or 'last_name' in change):
            state = send_adams_post_request(registration.event, [registration], update=True)[0]
            if state == CERNAccessRequestState.active:
                registration.cern_access_request.request_state = state

    def _event_title_changed(self, event, changes, **kwargs):
        """Update event name in the ADaMS CERN access request."""
        if 'title' not in changes:
            return

        requested_registrations = get_requested_registrations(event=event, only_active=True)
        if requested_registrations:
            state = send_adams_post_request(event, requested_registrations, update=True)[0]
            if state == CERNAccessRequestState.active:
                update_access_requests(requested_registrations, state)

    def _is_ticketing_handled(self, regform, **kwargs):
        """
        Check if the registration form is used for CERN access and thus
        should not send tickets automatically.
        """
        return regform.cern_access_request is not None and regform.cern_access_request.is_active

    def _is_ticket_blocked(self, registration, **kwargs):
        """Check if the user should be prevented from downloading the ticket manually."""
        regform = registration.registration_form
        # if we don't handle ticketing (no active access request) we never block tickets
        if not self._is_ticketing_handled(regform):
            return False
        # if ticket downloads are disabled and the user is not a manager, block ticket downloads
        # skipping this check for managers is needed so they can generate tickets using the
        # management area
        if (not regform.ticket_on_event_page and not regform.ticket_on_summary_page and not
                registration.event.can_manage(session.user, 'registration')):
            return True
        # if the request does not have personal data we always block the tickets, even for
        # a manager since they are not supposed to get tickets for people who didn't provide
        # the required personal data
        req = registration.cern_access_request
        return not req or not req.is_active or not req.has_identity_info

    def _form_validated(self, form, **kwargs):
        """
        Forbid to disable the tickets when access to CERN is requested and
        to use CERN access ticket template with regforms without active CERN access request.
        """
        if not isinstance(form, TicketsForm):
            return

        regform = RegistrationForm.get_or_404(request.view_args['reg_form_id'])
        if not form.tickets_enabled.data:
            if not regform.cern_access_request or not regform.cern_access_request.is_active:
                return
            err = _('This form is used to grant CERN site access so ticketing must be enabled')
            form.tickets_enabled.errors.append(err)
            return False
        access_tpl = self.settings.get('access_ticket_template')
        ticket_template = DesignerTemplate.get_or_404(form.ticket_template_id.data)
        if not access_tpl:
            return
        if ticket_template == access_tpl or ticket_template.backside_template == access_tpl:
            if (not regform.cern_access_request or
                    (regform.cern_access_request and
                        regform.cern_access_request.request_state != CERNAccessRequestState.active)):
                form.ticket_template_id.errors.append(_('The selected template can only be used with an '
                                                        'active CERN access request'))
                return False

    def _print_badge_template(self, template, regform, **kwargs):
        access_tpl = self.settings.get('access_ticket_template')
        if not access_tpl:
            return
        if template == access_tpl or template.backside_template == access_tpl:
            if (not regform.cern_access_request or
                    (regform.cern_access_request and
                        regform.cern_access_request.request_state != CERNAccessRequestState.active)):
                raise Forbidden(_('This badge cannot be printed because it uses the CERN access ticket '
                                  'template without an active CERN access request'))

    def _generate_ticket_qr_code(self, registration, ticket_data, **kwargs):
        if not self._is_ticketing_handled(registration.registration_form):
            return
        event = registration.event
        ticket_data.update(build_access_request_data(registration, event, generate_code=False, for_qr_code=True))

    def _get_designer_placeholders(self, sender, **kwargs):
        yield TicketAccessDatesPlaceholder
        yield TicketLicensePlatePlaceholder

    def _get_email_placeholders(self, sender, **kwargs):
        yield FirstNamePlaceholder
        yield LastNamePlaceholder
        yield EventTitlePlaceholder
        yield FormLinkPlaceholder
        yield AccessPeriodPlaceholder
