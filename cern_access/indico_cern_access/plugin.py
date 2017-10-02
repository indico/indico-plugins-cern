from __future__ import unicode_literals

from flask import request
from flask_pluginengine import render_plugin_template
from pytz import timezone
from werkzeug.exceptions import Forbidden
from wtforms import StringField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import SettingConverter
from indico.modules.designer import TemplateType
from indico.modules.designer.models.templates import DesignerTemplate
from indico.modules.events import Event
from indico.modules.events.registration.forms import TicketsForm
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.util.string import remove_accents, unicode_to_ascii
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField, MultipleItemsField, PrincipalListField

from indico_cern_access import _
from indico_cern_access.blueprint import blueprint
from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.util import (create_access_request, generate_access_id, get_event_registrations,
                                     get_random_reservation_code, get_requested_forms, notify_access_withdrawn,
                                     send_adams_delete_request, send_adams_post_request, send_tickets,
                                     update_access_requests, withdraw_access_requests)


class PluginSettingsForm(IndicoForm):
    adams_url = URLField(_('ADaMS URL'), [DataRequired()],
                         description=_('The URL of the ADaMS REST API'))
    authorized_users = PrincipalListField(_('Authorized_users'), groups=True,
                                          description=_('List of users/groups who can send requests'))
    excluded_categories = MultipleItemsField('Excluded categories', fields=[{'id': 'id', 'caption': 'Category ID'}])
    login = StringField(_('Login'), [DataRequired()],
                        description=_('The login used to authenticate with ADaMS service'))
    password = IndicoPasswordField(_('Password'), [DataRequired()],
                                   description=_('The password used to authenticate with ADaMS service'))
    secret_key = StringField(_('Secret key'), [DataRequired()],
                             description=_('Secret key to sign requests to ADaMS API'))
    access_ticket_template_id = QuerySelectField(_("Access ticket template"), allow_blank=True,
                                                 blank_text=_("No access ticket selected"), get_label='title',
                                                 description=_("Ticket template allowing access to CERN"))

    def __init__(self, *args, **kwargs):
        super(PluginSettingsForm, self).__init__(*args, **kwargs)
        self.access_ticket_template_id.query = (DesignerTemplate.query
                                                .filter(DesignerTemplate.category_id == 0,
                                                        DesignerTemplate.type == TemplateType.badge))


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
    default_settings = {'adams_url': 'https://oraweb.cern.ch/ords/devdb11/adams3/api/bookings/',
                        'login': 'indicoprod',
                        'password': '',
                        'secret_key': '',
                        'access_ticket_template_id': None,
                        'excluded_categories': []}
    settings_converters = {
        'access_ticket_template_id': DesignerTemplateConverter
    }
    acl_settings = {'authorized_users'}

    def init(self):
        super(CERNAccessPlugin, self).init()
        self.template_hook('registration_access_status', self._get_access_status)
        self.inject_js('cern_access_js', WPRequestsEventManagement)
        self.inject_css('cern_access_css', WPRequestsEventManagement)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.event.registration_deleted, self._registration_deleted)
        self.connect(signals.event.registration_state_updated, self._registration_state_changed)
        self.connect(signals.event.timetable.times_changed, self._event_time_changed, sender=Event)
        self.connect(signals.event.registration_personal_data_modified, self._registration_modified)
        self.connect(signals.event.registration_form_deleted, self._registration_form_deleted)
        self.connect(signals.event.deleted, self._event_deleted)
        self.connect(signals.event.updated, self._event_title_changed)
        self.connect(signals.event.is_ticketing_handled, self._is_ticketing_handled)
        self.connect(signals.form_validated, self._form_validated)
        self.connect(signals.event.designer.print_badge_template, self._print_badge_template)
        self.connect(signals.event.registration.generate_ticket_qr_code, self._generate_ticket_qr_code)

    def get_blueprints(self):
        yield blueprint

    def register_assets(self):
        self.register_js_bundle('cern_access_js', 'js/cern_access.js')
        self.register_css_bundle('cern_access_css', 'css/cern_access.scss')

    def _get_event_request_definitions(self, sender, **kwargs):
        return CERNAccessRequestDefinition

    def _get_access_status(self, registration, **kwargs):
        return render_plugin_template('cern_access_status.html',
                                      registration=registration,
                                      access_state=CERNAccessRequestState)

    def _registration_deleted(self, registration, **kwargs):
        """Withdraws CERN access request for deleted registrations"""
        if registration.cern_access_request:
            send_adams_delete_request([registration])
            registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_state_changed(self, registration, **kwargs):
        """Requests/withdraws CERN access for registrations that changed their state"""
        access_request_regform = registration.registration_form.cern_access_request
        is_form_requested = access_request_regform and access_request_regform.is_active
        is_registration_requested = registration.cern_access_request and registration.cern_access_request.is_active
        if not is_form_requested:
            return
        if registration.state == RegistrationState.complete:
            if not is_registration_requested:
                event = registration.registration_form.event_new
                state, data = send_adams_post_request(event, [registration])
                create_access_request(registration, state, data[registration.id]["$rc"])
                if state == CERNAccessRequestState.accepted and registration.registration_form.ticket_on_email:
                    send_tickets([registration])
        elif registration.state == RegistrationState.unpaid:
            if access_request_regform.allow_unpaid and not is_registration_requested:
                state, data = send_adams_post_request(registration.event_new, [registration])
                create_access_request(registration, state, data[registration.id]["$rc"])
                if state == CERNAccessRequestState.accepted and registration.registration_form.ticket_on_email:
                    send_tickets([registration])
            elif not access_request_regform.allow_unpaid and is_registration_requested:
                send_adams_delete_request([registration])
                registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        elif is_registration_requested:
            send_adams_delete_request([registration])
            registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_time_changed(self, event, obj, **kwargs):
        """Updates event time in CERN access requests in ADaMS"""
        registrations = get_event_registrations(event=obj, requested=True)
        if registrations:
            state, _ = send_adams_post_request(obj, registrations, update=True)
            if state == CERNAccessRequestState.accepted:
                update_access_requests(registrations, state)

    def _registration_form_deleted(self, registration_form):
        """Withdraws CERN access request for deleted registration form and corresponding registrations"""
        if registration_form.cern_access_request and registration_form.cern_access_request.is_active:
            registrations = get_event_registrations(registration_form.event_new, regform=registration_form, requested=True)
            if registrations:
                deleted = send_adams_delete_request(registrations)
                if deleted:
                    withdraw_access_requests(registrations)
                    notify_access_withdrawn(registrations)
            registration_form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_deleted(self, event, user):
        """Withdraws CERN access request for registration forms and corresponding registrations of deleted event"""
        access_requests_forms = get_requested_forms(event)
        if access_requests_forms:
            requested_registrations = get_event_registrations(event=event, requested=True)
            if requested_registrations:
                deleted = send_adams_delete_request(requested_registrations)
                if deleted:
                    withdraw_access_requests(requested_registrations)
                    notify_access_withdrawn(requested_registrations)
            for form in access_requests_forms:
                form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_modified(self, registration, change):
        """If name of registration changed, updates the ADaMS CERN access request"""
        if registration.cern_access_request and ('first_name' in change.keys() or 'last_name' in change.keys()):
            state, _ = send_adams_post_request(registration.event_new, [registration], update=True)
            if state == CERNAccessRequestState.accepted:
                registration.cern_access_request.request_state = state

    def _event_title_changed(self, event, changes, **kwargs):
        """Updates event name in the ADaMS CERN access request"""
        if 'title' not in changes:
            return
        requested_registrations = get_event_registrations(event=event, requested=True)
        if requested_registrations:
            state, _ = send_adams_post_request(event, requested_registrations, update=True)
            if state == CERNAccessRequestState.accepted:
                update_access_requests(requested_registrations, state)

    def _is_ticketing_handled(self, regform):
        """Checks if a registration form has requested access to CERN, if so the plugin will handle tickets mailing """
        if regform.cern_access_request and regform.cern_access_request.is_active:
            return True
        return False

    def _form_validated(self, form, **kwargs):
        """Forbids to disable the tickets when access to CERN is requested and
         to use CERN access ticket template with regforms without accepted CERN access request
        """
        if not isinstance(form, TicketsForm):
            return
        regform = RegistrationForm.get_one(request.view_args['reg_form_id'])
        if regform.cern_access_request and regform.cern_access_request.is_active and form.tickets_enabled.data is False:
            error = 'Access to CERN is requested for participants registered with this form, ticketing must be enabled'
            form.tickets_enabled.errors.append(error)
            return False
        access_tpl = self.settings.get('access_ticket_template_id')
        ticket_template = DesignerTemplate.get_one(form.ticket_template_id.data)
        if not access_tpl:
            return
        if ticket_template == access_tpl or ticket_template.backside_template == access_tpl:
            if (not regform.cern_access_request or regform.cern_access_request and
                    regform.cern_access_request.request_state != CERNAccessRequestState.accepted):
                form.ticket_template_id.errors.append(_('Selected template can only be used with an '
                                                        'accepted CERN access request'))
                return False

    def _print_badge_template(self, template, **kwargs):
        access_tpl = self.settings.get('access_ticket_template_id')
        if not access_tpl:
            return
        regform = kwargs.get('regform')
        if template == access_tpl or template.backside_template == access_tpl:
            if (not regform.cern_access_request or
                    regform.cern_access_request and
                    regform.cern_access_request.request_state != CERNAccessRequestState.accepted):
                raise Forbidden('This badge cannot be printed because it uses the CERN access ticket '
                                'template without an accepted CERN access request')

    def _generate_ticket_qr_code(self, registration, ticket_data, **kwargs):
        event = registration.event_new
        tz = timezone('Europe/Zurich')
        ticket_data.update({
            '$id': generate_access_id(registration.id),
            '$rc': get_random_reservation_code(),
            '$gn': unicode_to_ascii(remove_accents(event.title)),
            '$fn': unicode_to_ascii(remove_accents(registration.first_name)),
            '$ln': unicode_to_ascii(remove_accents(registration.last_name)),
            '$sd': event.start_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M'),
            '$ed': event.end_dt.astimezone(tz).strftime('%Y-%m-%dT%H:%M')
        })
