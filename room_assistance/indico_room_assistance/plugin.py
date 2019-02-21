# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask_pluginengine import url_for_plugin

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin
from indico.modules.rb_new.views.base import WPRoomBookingBase
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField
from indico.web.menu import TopMenuItem

from indico_room_assistance import _
from indico_room_assistance.blueprint import blueprint
from indico_room_assistance.models.room_assistance_requests import RoomAssistanceRequest


class RoomAssistanceForm(IndicoForm):
    room_assistance_recipients = EmailListField(_('Recipients'))


class RoomAssistanceRequestPlugin(IndicoPlugin):
    """Room assistance request

    Provides a service request where users can ask
    for startup assistance with their booking.
    """

    configurable = True
    settings_form = RoomAssistanceForm
    default_settings = {
        'room_assistance_recipients': [],
    }

    def init(self):
        super(RoomAssistanceRequestPlugin, self).init()
        self.connect(signals.menu.items, self._extend_services_menu, sender='top-menu')
        self.connect(signals.rb.booking_created, self._create_request_if_necessary)
        self.inject_bundle('react.js', WPRoomBookingBase)
        self.inject_bundle('semantic-ui.js', WPRoomBookingBase)
        self.inject_bundle('room_assistance.js', WPRoomBookingBase)
        self.inject_bundle('room_assistance.css', WPRoomBookingBase)

    def get_blueprints(self):
        return blueprint

    def _extend_services_menu(self, reservation, **kwargs):
        return TopMenuItem('services-cern-room-assistance', _('Room assistance'),
                           url_for_plugin('room_assistance.request_list'), section='services')

    def _create_request_if_necessary(self, reservation, extra_fields, **kwargs):
        if not extra_fields:
            return

        should_create_request = extra_fields.get('notification_for_assistance')
        if not should_create_request:
            return

        reservation.room_assistance_request = RoomAssistanceRequest()
        db.session.flush()
