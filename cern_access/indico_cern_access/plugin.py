from __future__ import unicode_literals

from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.events import Event
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalListField

from indico_cern_access import _
from indico_cern_access.blueprint import blueprint
from indico_cern_access.definition import CERNAccessRequestDefinition
from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.util import (create_access_request, get_event_registrations, get_requested_forms,
                                     notify_access_withdrawn, send_adams_delete_request, send_adams_post_request,
                                     update_access_requests, withdraw_access_requests)


class PluginSettingsForm(IndicoForm):
    adams_url = URLField(_('ADaMS URL'), [DataRequired()], description=_("The URL of the ADaMS REST API"))
    authorized_users = PrincipalListField(_('Authorized_users'), groups=True,
                                          description=_('List of users/groups who can send requests'))


class CERNAccessPlugin(IndicoPlugin):
    """CERN Access Request

    Provides a service request through which event managers can ask for
    access to the CERN site for the participants of the event
    """

    settings_form = PluginSettingsForm
    configurable = True
    default_settings = {'adams_url': 'https://oraweb.cern.ch/ords/devdb11/adams3/api/bookings/'}
    acl_settings = {'authorized_users'}

    def init(self):
        super(CERNAccessPlugin, self).init()
        self.inject_js('cern_access_js', WPRequestsEventManagement)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.event.registration_deleted, self._registration_deleted)
        self.connect(signals.event.registration_state_updated, self._registration_state_changed)
        self.connect(signals.event.timetable.times_changed, self._event_time_changed, sender=Event)
        self.connect(signals.event.registration_personal_data_modified, self._registration_modified)
        self.connect(signals.event.registration_form_deleted, self._registration_form_deleted)
        self.connect(signals.event.deleted, self._event_deleted)

    def get_blueprints(self):
        yield blueprint

    def register_assets(self):
        self.register_js_bundle('cern_access_js', 'js/cern_access.js')

    def _get_event_request_definitions(self, sender, **kwargs):
        return CERNAccessRequestDefinition

    def _registration_deleted(self, registration, **kwargs):
        if registration.cern_access_request:
            send_adams_delete_request([registration])
            registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _registration_state_changed(self, registration, **kwargs):
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
        elif registration.state == RegistrationState.unpaid:
            if access_request_regform.allow_unpaid and not is_registration_requested:
                state, data = send_adams_post_request(registration.event_new, [registration])
                create_access_request(registration, state, data[registration.id]["$rc"])
            elif not access_request_regform.allow_unpaid and is_registration_requested:
                send_adams_delete_request([registration])
                registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn
        elif is_registration_requested:
            send_adams_delete_request([registration])
            registration.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_time_changed(self, event, obj, **kwargs):
        registrations = get_event_registrations(event=obj, requested=True)
        if registrations:
            state, _ = send_adams_post_request(obj, registrations, update=True)
            update_access_requests(registrations, state)

    def _registration_form_deleted(self, registration_form):
        if registration_form.cern_access_request and registration_form.cern_access_request.is_active:
            registrations = get_event_registrations(registration_form.event_new, regform=registration_form, requested=True)
            if registrations:
                deleted = send_adams_delete_request(registrations)
                if deleted:
                    withdraw_access_requests(registrations)
                    notify_access_withdrawn(registrations)
            registration_form.cern_access_request.request_state = CERNAccessRequestState.withdrawn

    def _event_deleted(self, event, user):
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
        if registration.cern_access_request and ('first_name' in change.keys() or 'last_name' in change.keys()):
            state, _ = send_adams_post_request(registration.event_new, [registration], update=True)
            registration.cern_access_request.request_state = state
