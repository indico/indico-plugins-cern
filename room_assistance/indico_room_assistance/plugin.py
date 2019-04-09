# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import session
from flask_pluginengine import render_plugin_template, url_for_plugin

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import ModelListConverter
from indico.modules.rb.models.rooms import Room
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, IndicoQuerySelectMultipleField, PrincipalListField
from indico.web.menu import TopMenuItem

from indico_room_assistance import _
from indico_room_assistance.blueprint import blueprint
from indico_room_assistance.definition import RoomAssistanceRequest
from indico_room_assistance.util import is_room_assistance_support


def _order_func(object_list):
    return sorted(object_list, key=lambda r: natural_sort_key(r[1].full_name))


class RoomAssistanceForm(IndicoForm):
    _fieldsets = [
        ('Startup assistance emails', ['room_assistance_recipients', 'rooms_with_assistance',
                                       'room_assistance_support']),
    ]

    room_assistance_recipients = EmailListField(_('Recipients'),
                                                description=_('Notifications about room assistance requests are sent '
                                                              'to these email addresses (one per line)'))
    rooms_with_assistance = IndicoQuerySelectMultipleField('Rooms',
                                                           query_factory=lambda: Room.query,
                                                           description=_('Rooms for which users can request startup '
                                                                         'assistance'),
                                                           get_label='full_name', collection_class=set,
                                                           render_kw={'size': 20}, modify_object_list=_order_func)
    room_assistance_support = PrincipalListField(_('Room assistance support'), groups=True,
                                                 description=_('List of users who can view the list of events with '
                                                               'room startup assistance.'))


class RoomAssistancePlugin(IndicoPlugin):
    """Room assistance request

    This plugin lets users request assistance for meeting rooms.
    """

    configurable = True
    settings_form = RoomAssistanceForm
    settings_converters = {
        'rooms_with_assistance': ModelListConverter(Room)
    }
    acl_settings = {'room_assistance_support'}
    default_settings = {
        'room_assistance_recipients': [],
        'rooms_with_assistance': [],
    }

    def init(self):
        super(RoomAssistancePlugin, self).init()
        self.template_hook('event-actions', self._room_assistance_action)
        self.connect(signals.menu.items, self._extend_services_menu, sender='top-menu')
        self.connect(signals.plugin.get_event_request_definitions, self._get_room_assistance_request)

    def get_blueprints(self):
        return blueprint

    def _room_assistance_action(self, event, **kwargs):
        has_room_assistance_request = event.requests.filter_by(type='room-assistance').has_rows()
        room_allows_assistance = event.room is not None and event.room in self.settings.get('rooms_with_assistance')
        can_request_assistance = not event.has_ended and not has_room_assistance_request and room_allows_assistance
        return render_plugin_template('room_assistance_action.html', event=event,
                                      can_request_assistance=can_request_assistance)

    def _extend_services_menu(self, reservation, **kwargs):
        if not session.user or not is_room_assistance_support(session.user):
            return

        return TopMenuItem('services-cern-room-assistance', _('Room assistance'),
                           url_for_plugin('room_assistance.request_list'), section='services')

    def _get_room_assistance_request(self, sender, **kwargs):
        return RoomAssistanceRequest
