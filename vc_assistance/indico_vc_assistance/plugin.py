# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import flash, session
from flask_pluginengine import render_plugin_template, url_for_plugin
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import ModelConverter
from indico.modules.events import Event
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.rb.models.room_features import RoomFeature
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalListField
from indico.web.http_api import HTTPAPIHook
from indico.web.menu import TopMenuItem

from indico_vc_assistance import _
from indico_vc_assistance.api import RoomVCListHook, VCAssistanceExportHook
from indico_vc_assistance.blueprint import blueprint
from indico_vc_assistance.definition import VCAssistanceRequest
from indico_vc_assistance.util import has_vc_rooms_attached_to_capable, is_vc_support, start_time_within_working_hours
from indico_vc_assistance.views import WPVCAssistance


class PluginSettingsForm(IndicoForm):
    authorized = PrincipalListField(_('Authorized users'), allow_groups=True,
                                    description=_('List of users who can request videoconference assistance.'))
    vc_support = PrincipalListField(_('Videoconference support'), allow_groups=True,
                                    description=_('List of users who can view the list of events with videoconference '
                                                  'assistance.'))
    support_email = EmailField(_('Support email'), [DataRequired()],
                               description=_('Videoconference email support address'))
    room_feature = QuerySelectField(_("Room feature"), [DataRequired()], allow_blank=True,
                                    query_factory=lambda: RoomFeature.query, get_label='title',
                                    description=_("The feature indicating that a room supports videoconference."))


class VCAssistanceRequestPlugin(IndicoPlugin):
    """Videoconference Assistance Request

    Provides a service request where participants can ask for their
    event to have videoconference assistance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {
        'support_email': '',
        'room_feature': None,
    }
    acl_settings = {'authorized', 'vc_support'}
    settings_converters = {
        'room_feature': ModelConverter(RoomFeature),
    }

    def init(self):
        super(VCAssistanceRequestPlugin, self).init()
        self.inject_bundle('main.css', WPVCAssistance)
        self.template_hook('before-vc-list', self._get_vc_assistance_request_link)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.acl.can_access, self._can_access_event, sender=Event)
        self.connect(signals.event.updated, self._event_updated)
        self.connect(signals.menu.items, self._extend_top_menu, sender='top-menu')
        HTTPAPIHook.register(VCAssistanceExportHook)
        HTTPAPIHook.register(RoomVCListHook)

    def get_blueprints(self):
        return blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return VCAssistanceRequest

    def _can_access_event(self, sender, user, **kwargs):
        if user is not None and is_vc_support(user):
            return True

    def _extend_top_menu(self, sender, **kwargs):
        if not session.user or not is_vc_support(session.user):
            return
        return TopMenuItem('services-cern-vc-assistance', _('Videoconference assistance'),
                           url_for_plugin('vc_assistance.request_list'), section='services')

    def _get_vc_assistance_request_link(self, event, **kwargs):
        from definition import VCAssistanceRequest
        req = Request.find_latest_for_event(event, VCAssistanceRequest.name)
        support_email = VCAssistanceRequestPlugin.settings.get('support_email')
        return render_plugin_template('vc_assistance_request_link.html', event=event, name=VCAssistanceRequest.name,
                                      request_accepted=req is not None and req.state == RequestState.accepted,
                                      has_capable_vc_room_attached=has_vc_rooms_attached_to_capable(event),
                                      support_email=support_email)

    def _event_updated(self, event, changes, **kwargs):
        req = Request.find_latest_for_event(event, VCAssistanceRequest.name)
        if not req or req.state != RequestState.accepted:
            return
        if 'start_dt' in changes and not start_time_within_working_hours(event):
            flash(_("The new event start time is out of working hours so videoconference assistance cannot be "
                    "provided."), 'warning')
        if 'location_data' in changes and not has_vc_rooms_attached_to_capable(event):
            flash(_("The new event location doesn't have videoconference capabilities so videoconference "
                    "assistance cannot be provided."), 'warning')
