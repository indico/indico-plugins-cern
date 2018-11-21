# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import session
from flask_pluginengine import url_for_plugin

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalListField
from indico.web.menu import TopMenuItem

from indico_vc_assistance import _
from indico_vc_assistance.blueprint import blueprint
from indico_vc_assistance.definition import VCRequest
from indico_vc_assistance.util import is_vc_support


class PluginSettingsForm(IndicoForm):
    managers = PrincipalListField(_('Managers'), groups=True,
                                  description=_('List of users who can request videoconference assistance.'))
    vc_support = PrincipalListField(_('Videoconference support'), groups=True,
                                    description=_('List of users who can view the list of events with videoconference '
                                                  'assistance.'))


class VCRequestsPlugin(IndicoPlugin):
    """Videoconference Assistance Request

    Provides a service request where participants can ask for their
    event to have videoconference assistance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    acl_settings = {'authorized', 'vc_support'}

    def init(self):
        super(VCRequestsPlugin, self).init()
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.menu.items, self._extend_top_menu, sender='top-menu')

    def get_blueprints(self):
        return blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return VCRequest

    def _extend_top_menu(self, sender, **kwargs):
        if not session.user or not is_vc_support(session.user):
            return
        return TopMenuItem('services-cern-vc-assistance', _('Videoconference assistance'),
                           url_for_plugin('vc_assistance.request_list'), section='services')
