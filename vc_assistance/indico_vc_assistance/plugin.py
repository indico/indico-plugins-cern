# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import session
from flask_pluginengine import url_for_plugin, render_plugin_template

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalListField
from indico.web.menu import TopMenuItem

from indico_vc_assistance import _
from indico_vc_assistance.blueprint import blueprint
from indico_vc_assistance.definition import VCAssistanceRequest
from indico_vc_assistance.util import is_vc_support, has_room_with_vc_attached


class PluginSettingsForm(IndicoForm):
    managers = PrincipalListField(_('Managers'), groups=True,
                                  description=_('List of users who can request videoconference assistance.'))
    vc_support = PrincipalListField(_('Videoconference support'), groups=True,
                                    description=_('List of users who can view the list of events with videoconference '
                                                  'assistance.'))


class VCAssistanceRequestPlugin(IndicoPlugin):
    """Videoconference Assistance Request

    Provides a service request where participants can ask for their
    event to have videoconference assistance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    acl_settings = {'authorized', 'vc_support'}

    def init(self):
        super(VCAssistanceRequestPlugin, self).init()
        self.template_hook('before-vc-list', self._get_vc_assistance_request_link)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.menu.items, self._extend_top_menu, sender='top-menu')

    def get_blueprints(self):
        return blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return VCAssistanceRequest

    def _extend_top_menu(self, sender, **kwargs):
        if not session.user or not is_vc_support(session.user):
            return
        return TopMenuItem('services-cern-vc-assistance', _('Videoconference assistance'),
                           url_for_plugin('vc_assistance.request_list'), section='services')

    def _get_vc_assistance_request_link(self, event):
        from definition import VCAssistanceRequest
        req = Request.find_latest_for_event(event, VCAssistanceRequest.name)
        has_vc_room_attached = has_room_with_vc_attached(event)
        return render_plugin_template('vc_assistance_request_link.html', req=req,
                                      request_accepted=req.state == RequestState.accepted,
                                      has_vc_room_attached=has_vc_room_attached)
