# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import timedelta

import dateutil.parser
from flask_pluginengine import plugin_context
from werkzeug.exceptions import Forbidden

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState
from indico.web.forms.base import FormDefaults

from indico_room_assistance import _
from indico_room_assistance.forms import RoomAssistanceRequestForm
from indico_room_assistance.notifications import (notify_about_new_request, notify_about_request_modification,
                                                  notify_about_withdrawn_request)


class RoomAssistanceRequest(RequestDefinitionBase):
    name = 'room-assistance'
    title = _('Room assistance')
    form = RoomAssistanceRequestForm

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['event_has_room_attached'] = event.room is not None
        kwargs['room_allows_assistance'] = event.room in cls.plugin.settings.get('rooms_with_assistance')
        return super(RoomAssistanceRequest, cls).render_form(event, **kwargs)

    @classmethod
    def create_form(cls, event, existing_request=None):
        form_data = {'start_dt': event.start_dt_local - timedelta(minutes=30)}
        if existing_request:
            form_data = dict(existing_request.data)
            if form_data['start_dt']:
                form_data['start_dt'] = dateutil.parser.parse(form_data['start_dt'])
        with plugin_context(cls.plugin):
            return cls.form(prefix='request-', obj=FormDefaults(form_data), event=event, request=existing_request)

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def send(cls, req, data):
        room = req.event.room
        if room is None or room not in cls.plugin.settings.get('rooms_with_assistance'):
            raise Forbidden

        data['start_dt'] = data['start_dt'].isoformat()
        is_new = req.id is None
        req.state = RequestState.accepted
        old_data = {} if is_new else req.data

        super(RoomAssistanceRequest, cls).send(req, data)
        with plugin_context(cls.plugin):
            if is_new:
                notify_about_new_request(req)
            else:
                changes = {}
                if data['reason'] != old_data['reason']:
                    changes['reason'] = {'old': old_data['reason'], 'new': data['reason']}
                if data['start_dt'] != old_data['start_dt']:
                    changes['start_dt'] = {'old': dateutil.parser.parse(old_data['start_dt']),
                                           'new': dateutil.parser.parse(data['start_dt'])}
                if changes:
                    notify_about_request_modification(req, changes)

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        super(RoomAssistanceRequest, cls).withdraw(req, notify_event_managers)
        with plugin_context(cls.plugin):
            notify_about_withdrawn_request(req)
