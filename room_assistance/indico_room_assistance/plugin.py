# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime

import dateutil.parser
import pytz
from flask import flash, request, session
from flask_pluginengine import render_plugin_template, url_for_plugin

from indico.core import signals
from indico.core.config import config
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import ModelListConverter
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.modules.rb.models.rooms import Room
from indico.modules.users import User
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, IndicoQuerySelectMultipleField, PrincipalListField
from indico.web.menu import TopMenuItem

from indico_room_assistance import _
from indico_room_assistance.blueprint import blueprint
from indico_room_assistance.definition import RoomAssistanceRequest
from indico_room_assistance.util import (can_request_assistance_for_event, event_has_room_with_support_attached,
                                         is_room_assistance_support)


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
        self.inject_bundle('main.css', WPRequestsEventManagement, subclasses=False,
                           condition=lambda: request.view_args.get('type') == RoomAssistanceRequest.name)
        self.template_hook('event-actions', self._room_assistance_action)
        self.connect(signals.menu.items, self._extend_services_menu, sender='top-menu')
        self.connect(signals.plugin.get_event_request_definitions, self._get_room_assistance_request)
        self.connect(signals.event.updated, self._on_event_update)

    def get_blueprints(self):
        return blueprint

    def _room_assistance_action(self, event, **kwargs):
        return render_plugin_template('room_assistance_action.html', event=event,
                                      can_request_assistance=can_request_assistance_for_event(event))

    def _extend_services_menu(self, reservation, **kwargs):
        if not session.user or not is_room_assistance_support(session.user):
            return

        return TopMenuItem('services-cern-room-assistance', _('Room assistance'),
                           url_for_plugin('room_assistance.request_list'), section='services')

    def _get_room_assistance_request(self, sender, **kwargs):
        return RoomAssistanceRequest

    def _on_event_update(self, event, **kwargs):
        changes = kwargs['changes']
        if not changes.viewkeys() & {'location_data', 'start_dt', 'end_dt'}:
            return

        request = Request.find_latest_for_event(event, RoomAssistanceRequest.name)
        if not request or request.state != RequestState.accepted:
            return

        if 'location_data' in changes and not event_has_room_with_support_attached(event):
            request.definition.reject(request, {'comment': render_plugin_template('auto_reject_no_supported_room.txt')},
                                      User.get_system_user())
            request.data = dict(request.data, occurrences=[])
            flash(_("The new event location is not in the list of the rooms supported by the room assistance team. "
                    "Room assistance request has been rejected and support will not be provided."), 'warning')
        if changes.viewkeys() & {'start_dt', 'end_dt'}:
            tz = pytz.timezone(config.DEFAULT_TIMEZONE)
            occurrences = {dateutil.parser.parse(occ).astimezone(tz) for occ in request.data['occurrences']}
            req_dates = {occ.date() for occ in occurrences}
            event_dates = set(event.iter_days())
            old_dates = req_dates - event_dates
            has_overlapping_dates = req_dates & event_dates

            if not has_overlapping_dates:
                request.definition.reject(request,
                                          {'comment': render_plugin_template('auto_reject_no_overlapping_dates.txt')},
                                          User.get_system_user())
                request.data = dict(request.data, occurrences=[])
                flash(_("The new event dates don't overlap with the existing room assistance request for this event. "
                        "Room assistance request has been rejected and support will not be provided."), 'warning')
            elif old_dates and has_overlapping_dates:
                new_data = dict(request.data)
                new_data['occurrences'] = [occ.astimezone(pytz.utc).isoformat() for occ in occurrences
                                           if occ.date() in req_dates & event_dates]
                request.data = new_data
                flash(_("Room assistance had been requested for days that are not between the updated start/end "
                        "dates. Support will not be provided on these days anymore."), 'warning')
