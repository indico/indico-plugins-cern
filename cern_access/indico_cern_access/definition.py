# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import dateutil.parser
from flask import session
from flask_pluginengine import plugin_context

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState
from indico.web.forms.base import FormDefaults

from indico_cern_access import _
from indico_cern_access.forms import CERNAccessForm
from indico_cern_access.util import (check_access, get_access_dates, handle_event_time_update, is_authorized_user,
                                     is_category_blacklisted, update_access_request, withdraw_event_access_request)


class CERNAccessRequestDefinition(RequestDefinitionBase):
    name = 'cern-access'
    title = _('CERN Visitor Badges')
    form = CERNAccessForm

    @classmethod
    def create_form(cls, event, existing_request=None):
        default_data = cls.form_defaults
        if existing_request:
            default_data = dict(existing_request.data)
            if default_data['start_dt_override']:
                default_data['start_dt_override'] = dateutil.parser.parse(default_data['start_dt_override'])
            if default_data['end_dt_override']:
                default_data['end_dt_override'] = dateutil.parser.parse(default_data['end_dt_override'])
        with plugin_context(cls.plugin):
            return cls.form(prefix='request-', obj=FormDefaults(default_data), event=event, request=existing_request)

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['user_authorized'] = is_authorized_user(session.user)
        kwargs['category_blacklisted'] = is_category_blacklisted(event.category)
        return super(CERNAccessRequestDefinition, cls).render_form(event, **kwargs)

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def send(cls, req, data):
        check_access(req)
        start_dt = data['start_dt_override'] or req.event.start_dt
        end_dt = data['end_dt_override'] or req.event.end_dt
        if data['start_dt_override']:
            data['start_dt_override'] = data['start_dt_override'].isoformat()
        if data['end_dt_override']:
            data['end_dt_override'] = data['end_dt_override'].isoformat()
        times_changed = False
        if req.id is not None:
            old_start_dt, old_end_dt = get_access_dates(req)
            if old_start_dt != start_dt or old_end_dt != end_dt:
                times_changed = True
        super(CERNAccessRequestDefinition, cls).send(req, data)
        update_access_request(req)
        req.state = RequestState.accepted
        if times_changed:
            handle_event_time_update(req.event)

    @classmethod
    def withdraw(cls, req, notify_event_managers=False):
        check_access(req)
        withdraw_event_access_request(req)
        super(CERNAccessRequestDefinition, cls).withdraw(req, notify_event_managers)
