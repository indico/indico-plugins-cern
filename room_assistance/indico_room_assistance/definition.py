# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import dateutil.parser
import pytz
from flask_pluginengine import plugin_context
from werkzeug.exceptions import Forbidden

from indico.core.config import config
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
        return super().render_form(event, **kwargs)

    @classmethod
    def create_form(cls, event, existing_request=None):
        form_data = {'occurrences': None}
        if existing_request:
            tz = pytz.timezone(config.DEFAULT_TIMEZONE)
            form_data = dict(existing_request.data)
            form_data['occurrences'] = [dateutil.parser.parse(occ).astimezone(tz) for occ in form_data['occurrences']]
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

        is_new = req.id is None
        req.state = RequestState.accepted
        old_data = {} if is_new else req.data
        data['occurrences'] = [occ.astimezone(pytz.utc).isoformat() for occ in data['occurrences']]

        super().send(req, data)
        with plugin_context(cls.plugin):
            if is_new:
                notify_about_new_request(req)
            else:
                changes = {}
                if data['reason'] != old_data['reason']:
                    changes['reason'] = {'old': old_data['reason'], 'new': data['reason']}
                if data['occurrences'] != old_data['occurrences']:
                    changes['occurrences'] = [dateutil.parser.parse(occ) for occ in data['occurrences']]
                if changes:
                    notify_about_request_modification(req, changes)

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        super().withdraw(req, notify_event_managers)
        with plugin_context(cls.plugin):
            notify_about_withdrawn_request(req)
