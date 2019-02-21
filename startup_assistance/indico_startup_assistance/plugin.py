# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask_pluginengine import url_for_plugin

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.rb_new.views.base import WPRoomBookingBase
from indico.web.menu import TopMenuItem

from indico_startup_assistance import _
from indico_startup_assistance.blueprint import blueprint
from indico_startup_assistance.forms import StartupAssistanceForm
from indico_startup_assistance.operations import cancel_startup_assistance_request, create_startup_assistance_request


class StartupAssistanceRequestPlugin(IndicoPlugin):
    """Startup assistance request

    Provides a service request where users can ask
    for startup assistance with their booking.
    """

    configurable = True
    settings_form = StartupAssistanceForm
    default_settings = {
        'startup_assistance_recipients': [],
    }

    def init(self):
        super(StartupAssistanceRequestPlugin, self).init()
        self.connect(signals.menu.items, self._extend_services_menu, sender='top-menu')
        self.connect(signals.rb.booking_created, self._create_request_if_necessary)
        self.inject_bundle('react.js', WPRoomBookingBase)
        self.inject_bundle('semantic-ui.js', WPRoomBookingBase)
        self.inject_bundle('startup_assistance.js', WPRoomBookingBase)
        self.inject_bundle('startup_assistance.css', WPRoomBookingBase)

    def get_blueprints(self):
        return blueprint

    def _extend_services_menu(self, reservation, **kwargs):
        return TopMenuItem('services-cern-startup-assistance', _('Startup assistance'),
                           url_for_plugin('startup_assistance.request_list'), section='services')

    def _create_request_if_necessary(self, reservation, **kwargs):
        extra_fields = kwargs.get('extra_fields', {})
        if not extra_fields:
            return

        should_create_request = extra_fields.get('notificationForAssistance')
        if not should_create_request:
            return

        create_startup_assistance_request(reservation)
