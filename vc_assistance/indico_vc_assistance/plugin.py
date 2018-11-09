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
from indico.web.menu import TopMenuItem

from indico_vc_assistance import _
from indico_vc_assistance.blueprint import blueprint
from indico_vc_assistance.definition import VCRequest


class VCRequestsPlugin(IndicoPlugin):
    """Videoconference Assistance Request

    Provides a service request where event managers can ask for their
    event to have videoconference assistance.
    """

    def init(self):
        super(VCRequestsPlugin, self).init()
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.menu.items, self._extend_top_menu, sender='top-menu')

    def get_blueprints(self):
        return blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return VCRequest

    def _extend_top_menu(self, sender, **kwargs):
        if not session.user:
            return
        return TopMenuItem('services-cern-vc-assistance', _('Videoconference assistance'),
                           url_for_plugin('vc_assistance.request_list'), section='services')
