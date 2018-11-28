# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
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
from indico_vc_assistance.util import can_request_assistance, has_room_with_vc_attached


class VCAssistanceRequest(RequestDefinitionBase):
    name = 'vc-assistance'
    title = _('Videoconference assistance')
    form = VCAssistanceRequestForm

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['user_authorized'] = can_request_assistance(session.user)
        kwargs['has_vc_room_attached'] = has_room_with_vc_attached(event)
        req = kwargs['req']
        kwargs['request_accepted'] = req is not None and req.state == RequestState.accepted
        return super(VCAssistanceRequest, cls).render_form(event, **kwargs)

    @classmethod
    def send(cls, req, data):
        if not can_request_assistance(session.user):
            raise Forbidden
        super(VCAssistanceRequest, cls).send(req, data)
        req.state = RequestState.accepted
