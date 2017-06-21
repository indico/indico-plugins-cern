from __future__ import unicode_literals

from wtforms import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin
from indico.modules.events import Event
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.web.forms.base import IndicoForm

from indico_cern_access import _
from indico_cern_access.blueprint import blueprint
from indico_cern_access.definition import CernAccessRequest
from indico_cern_access.models.access_requests import AccessRequest
from indico_cern_access.models.regform_access_requests import RegformAccessRequest
from indico_cern_access.util import (delete_registrations, get_access_request, get_requested_accesses,
                                     get_requested_forms, get_requested_registrations, send_adams_delete_request,
                                     send_adams_post_request, update_registrations)


class PluginSettingsForm(IndicoForm):
    adams_url = URLField(_('ADAMS URL'), [DataRequired()], description=_("The URL to ADAMS requests"))
    id_prefix = StringField(_('Service prefix'), [DataRequired()], description=_('Service prefix for ADAMS request id'))


class CernAccessPlugin(IndicoPlugin):
    """CERN Access Request

    Provides a service request where event managers can ask for CERN access for participants of the event.
    """
    settings_form = PluginSettingsForm
    configurable = True
    default_settings = {'adams_url': 'https://oraweb.cern.ch/ords/devdb11/adams3/api/bookings/',
                        'id_prefix': 'in'}

    def init(self):
        super(CernAccessPlugin, self).init()
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.event.registration_deleted, self._registration_deleted)
        self.connect(signals.event.registration_state_updated, self._registration_state_changed)
        self.connect(signals.event.timetable.times_changed, self._event_time_changed, sender=Event)
        self.connect(signals.event.registration_personal_data_modified, self._registration_modified)
        self.connect(signals.event.registration_form_deleted, self._registration_form_deleted)
        self.connect(signals.event.deleted, self._event_deleted)

    def get_blueprints(self):
        yield blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return CernAccessRequest

    def _registration_deleted(self, registration, **kwargs):
        request = get_access_request(registration.id)
        if request:
            send_adams_delete_request(registration=registration)
            access_request = get_access_request(registration.id)
            db.session.delete(access_request)
            db.session.flush()

    def _registration_state_changed(self, registration, **kwargs):
        if registration.registration_form.access_request:
            if registration.state == RegistrationState.complete:
                if not registration.access_request:
                    event = Event.query.get(registration.event_id)
                    state, data = send_adams_post_request(event, registration=registration)
                    access_request = AccessRequest(registration_id=registration.id,
                                                   request_state=state,
                                                   reservation_code=data[registration.id]["$rc"])
                    db.session.add(access_request)
                    db.session.flush()
            elif registration.state == RegistrationState.unpaid:
                regform = RegformAccessRequest.query.get(registration.registration_form.id)
                if regform.allow_unpaid and not registration.access_request:
                        state, data = send_adams_post_request(registration.event_new, registration=registration)
                        access_request = AccessRequest(registration_id=registration.id,
                                                       request_state=state,
                                                       reservation_code=data[registration.id]["$rc"])
                        db.session.add(access_request)
                        db.session.flush()
                elif not regform.allow_unpaid and registration.access_request:
                        send_adams_delete_request(registration=registration)
                        db.session.delete(registration.access_request)
                        db.session.flush()
            elif RegistrationState.registration.access_request:
                    send_adams_delete_request(registration=registration)
                    db.session.delete(registration.access_request)
                    db.session.flush()

    def _event_time_changed(self, event, obj, **kwargs):
        registrations = get_requested_registrations(obj)
        if registrations:
            state, _ = send_adams_post_request(event=obj, registrations=registrations, update=True)
            update_registrations(registrations, state)

    def _registration_form_deleted(self, registration_form):
        if registration_form.access_request:
            access_requestes = get_requested_accesses(regform_id=registration_form.id)
            if access_requestes:
                deleted = send_adams_delete_request(access_requests=access_requestes)
                if deleted:
                    delete_registrations(access_requestes)
            db.session.delete(registration_form.access_request)

    def _event_deleted(self, event, user):
        form_access_requests = get_requested_forms(event)
        if form_access_requests:
            access_requestes = get_requested_accesses(event_id=event.id)
            if access_requestes:
                deleted = send_adams_delete_request(access_requests=access_requestes)
                if deleted:
                    delete_registrations(access_requestes)
            for form in form_access_requests:
                db.session.delete(form)

    def _registration_modified(self, registration, change):
        access_request = get_access_request(registration.id)
        if access_request and ('first_name' in change.keys() or 'last_name' in change.keys()):
            state, _ = send_adams_post_request(registration.event_new, registration=registration, update=True)
            access_request.state = state
            db.session.flush()
