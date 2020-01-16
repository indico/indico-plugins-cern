# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import session
from werkzeug.exceptions import Forbidden

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState

from indico_vc_assistance import _
from indico_vc_assistance.forms import VCAssistanceRequestForm
from indico_vc_assistance.util import (can_request_assistance, has_vc_capable_rooms, has_vc_rooms,
                                       has_vc_rooms_attached_to_capable, start_time_within_working_hours)


class VCAssistanceRequest(RequestDefinitionBase):
    name = 'vc-assistance'
    title = _('Videoconference assistance')
    form = VCAssistanceRequestForm

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def render_form(cls, event, **kwargs):
        from indico_vc_assistance.plugin import VCAssistanceRequestPlugin
        req = kwargs['req']
        kwargs['user_authorized'] = can_request_assistance(session.user)
        kwargs['has_vc_capable_rooms'] = has_vc_capable_rooms(event)
        kwargs['has_vc_rooms'] = has_vc_rooms(event)
        kwargs['has_vc_rooms_attached_to_capable'] = has_vc_rooms_attached_to_capable(event)
        kwargs['request_accepted'] = req is not None and req.state == RequestState.accepted
        kwargs['within_working_hours'] = start_time_within_working_hours(event)
        kwargs['support_email'] = VCAssistanceRequestPlugin.settings.get('support_email')
        return super(VCAssistanceRequest, cls).render_form(event, **kwargs)

    @classmethod
    def send(cls, req, data):
        if not can_request_assistance(session.user):
            raise Forbidden
        super(VCAssistanceRequest, cls).send(req, data)
        req.state = RequestState.accepted
