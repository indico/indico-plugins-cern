# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import time, timedelta

from flask import g, request, session
from flask_pluginengine import render_plugin_template
from werkzeug.exceptions import Forbidden
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.fields import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, Optional

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import DatetimeConverter, SettingConverter, TimedeltaConverter
from indico.modules.designer import TemplateType
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events import Event
from indico.modules.events.registration.forms import TicketsForm
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.placeholders.registrations import (EventTitlePlaceholder, FirstNamePlaceholder,
                                                                           LastNamePlaceholder)
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import (IndicoDateTimeField, IndicoPasswordField, MultipleItemsField, PrincipalListField,
                                     TimeDeltaField)

from indico_cern_access import _
from indico_cern_access.blueprint import blueprint
from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.forms import AccessIdentityDataForm, RegistrationFormPersonalDataForm
from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState
from indico_cern_access.placeholders import AccessPeriodPlaceholder, FormLinkPlaceholder, TicketAccessDatesPlaceholder
from indico_cern_access.util import (RegformDataMode, build_access_request_data, get_access_dates, get_last_request,
                                     get_requested_forms, get_requested_registrations, handle_event_time_update,
                                     notify_access_withdrawn, send_adams_delete_request, send_adams_post_request,
                                     update_access_requests, withdraw_access_requests)


class PluginSettingsForm(IndicoForm):
    adams_url = URLField(_('ADaMS URL'), [DataRequired()],
                         description=_('The URL of the ADaMS REST API'))
    username = StringField(_('Username'), [DataRequired()],
                           description=_('The login used to authenticate with ADaMS service'))
    password = IndicoPasswordField(_('Password'), [DataRequired()],
                                   description=_('The password used to authenticate with ADaMS service'))
    secret_key = IndicoPasswordField(_('Secret key'), [DataRequired()],
                                     description=_('Secret key to sign ADaMS requests'))
    authorized_users = PrincipalListField(_('Authorized users'), groups=True,
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

    def __init__(self, *args, **kwargs):
        super(PluginSettingsForm, self).__init__(*args, **kwargs)
        self.access_ticket_template.query = (DesignerTemplate.query
                                             .filter(DesignerTemplate.category_id == 0,
                                                     DesignerTemplate.type == TemplateType.badge)
                                             .order_by(db.func.lower(DesignerTemplate.title)))


class DesignerTemplateConverter(SettingConverter):
    """Convert a DesignerTemplate object to ID and backwards."""

    @staticmethod
    def from_python(value):
        return value.id

    @staticmethod
    def to_python(value):
        return DesignerTemplate.get(value)


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
        'secret_key': '',
        'excluded_categories': [],
        'access_ticket_template': None,
        'earliest_start_dt': None,
        'delete_personal_data_after': timedelta(days=180),
    }
    settings_converters = {
        'access_ticket_template': DesignerTemplateConverter,
        'earliest_start_dt': DatetimeConverter,
        'delete_personal_data_after': TimedeltaConverter,
    }
    acl_settings = {'authorized_users'}
    default_event_settings = {
        'email_subject': None,
        'email_body': None,
    }

    def init(self):
        super(CERNAccessPlugin, self).init()
        self.template_hook('registration-status-flag', self._get_access_status)
        self.template_hook('registration-status-action-button', self._get_access_action_button)
        self.template_hook('after-regform', self._get_personal_data_form)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.event.registration_deleted, self._registration_deleted)
        self.connect(signals.event.registration_created, self._registration_created)
        self.connect(signals.form_validated, self._registration_form_validated)
        self.connect(signals.event.timetable.times_changed, self._event_time_changed, sender=Event)
        self.connect(signals.event.registration_personal_data_modified, self._registration_modified)
        self.connect(signals.event.registration_form_deleted, self._registration_form_deleted)
        self.connect(signals.event.deleted, self._event_deleted)
        self.connect(signals.event.updated, self._event_title_changed)
        self.connect(signals.event.is_ticketing_handled, self._is_ticketing_handled)
        self.connect(signals.event.is_ticket_blocked, self._is_ticket_blocked)
        self.connect(signals.form_validated, self._form_validated)
        self.connect(signals.event.designer.print_badge_template, self._print_badge_template)
        self.connect(signals.event.registration.generate_ticket_qr_code, self._generate_ticket_qr_code)
        self.connect(signals.get_placeholders, self._get_designer_placeholders, sender='designer-fields')
        self.connect(signals.get_placeholders, self._get_email_placeholders, sender='cern-access-email')

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

    def _get_personal_data_form(self, event, regform, management, registration=None, **kwargs):
        if management or registration is not None:
            return

        if regform.cern_access_request and regform.cern_access_request.is_active:
            req = get_last_request(event)
            mode = req.data.get('regform_data_mode')
            if mode not in (RegformDataMode.during_registration, RegformDataMode.during_registration_required):
                return
            required = mode == RegformDataMode.during_registration_required
            form_cls = AccessIdentityDataForm if required else RegistrationFormPersonalDataForm
            form = g.get('personal_data_form') or form_cls()
            start_dt, end_dt = get_access_dates(req)
            return render_plugin_template('regform_identity_data_section.html', event=event, form=form,
                                          start_dt=start_dt, end_dt=end_dt, registration=registration,
                                          required=required)

    def _is_past_event(self, event):
        end_dt = get_access_dates(get_last_request(event))[1]
        return end_dt < now_utc()

    def _registration_deleted(self, registration, **kwargs):
        """Withdraw CERN access request for deleted registrations."""
        if registration.cern_access_request and not self._is_past_event(registration.event):
            send_adams_delete_request([registration])
            registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_created(self, registration, management, **kwargs):
        if management:
            return

        regform = registration.registration_form
        personal_data_form = g.pop('personal_data_form', None)

        if not regform.cern_access_request or not regform.cern_access_request.is_active or not personal_data_form:
            return

        req = get_last_request(registration.event)
        mode = req.data.get('regform_data_mode')
        if mode not in (RegformDataMode.during_registration, RegformDataMode.during_registration_required):
            return

        required = req.data.get('regform_data_mode') == RegformDataMode.during_registration_required
        if not required and not personal_data_form.request_cern_access.data:
            return

        registration.cern_access_request = CERNAccessRequest(birth_date=personal_data_form.birth_date.data,
                                                             nationality=personal_data_form.nationality.data,
                                                             birth_place=personal_data_form.birth_place.data,
                                                             request_state=CERNAccessRequestState.not_requested,
                                                             reservation_code='')

    def _registration_form_validated(self, form, **kwargs):
        if type(form).__name__ != 'RegistrationFormWTF':
            return

        req = get_last_request(g.rh.regform.event)
        if not req:
            return

        mode = req.data.get('regform_data_mode')
        if mode not in (RegformDataMode.during_registration, RegformDataMode.during_registration_required):
            return

        required = req.data.get('regform_data_mode') == RegformDataMode.during_registration_required
        form_cls = AccessIdentityDataForm if required else RegistrationFormPersonalDataForm
        g.personal_data_form = form = form_cls()
        if not form.validate_on_submit():
            return False

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
            registrations = get_requested_registrations(registration_form.event, regform=registration_form)
            if registrations:
                deleted = send_adams_delete_request(registrations)
                if deleted:
                    withdraw_access_requests(registrations)
                    notify_access_withdrawn(registrations)
            registration_form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_deleted(self, event, **kwargs):
        """
        Withdraw CERN access request for registration forms and corresponding
        registrations of deleted event.
        """
        access_requests_forms = get_requested_forms(event)
        if access_requests_forms and not self._is_past_event(event):
            requested_registrations = get_requested_registrations(event=event)
            if requested_registrations:
                deleted = send_adams_delete_request(requested_registrations)
                if deleted:
                    withdraw_access_requests(requested_registrations)
                    notify_access_withdrawn(requested_registrations)
            for form in access_requests_forms:
                form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_modified(self, registration, change, **kwargs):
        """If name of registration changed, updates the ADaMS CERN access request."""
        if registration.cern_access_request and ('first_name' in change or 'last_name' in change):
            state = send_adams_post_request(registration.event, [registration], update=True)[0]
            if state == CERNAccessRequestState.active:
                registration.cern_access_request.request_state = state

    def _event_title_changed(self, event, changes, **kwargs):
        """Update event name in the ADaMS CERN access request."""
        if 'title' not in changes:
            return

        requested_registrations = get_requested_registrations(event=event)
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

        regform = RegistrationForm.get_one(request.view_args['reg_form_id'])
        if regform.cern_access_request and regform.cern_access_request.is_active and not form.tickets_enabled.data:
            err = _('This form is used to grant CERN site access so ticketing must be enabled')
            form.tickets_enabled.errors.append(err)
            return False
        access_tpl = self.settings.get('access_ticket_template')
        ticket_template = DesignerTemplate.get_one(form.ticket_template_id.data)
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
        ticket_data.update(build_access_request_data(registration, event, generate_code=False))

    def _get_designer_placeholders(self, sender, **kwargs):
        yield TicketAccessDatesPlaceholder

    def _get_email_placeholders(self, sender, **kwargs):
        yield FirstNamePlaceholder
        yield LastNamePlaceholder
        yield EventTitlePlaceholder
        yield FormLinkPlaceholder
        yield AccessPeriodPlaceholder
