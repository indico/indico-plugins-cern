# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import dateutil.parser

from indico.core.config import config
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.modules.events.requests.models.requests import RequestState


def send_email_to_assistance(request, template_name, **template_params):
    from indico_room_assistance.plugin import RoomAssistancePlugin

    to_list = RoomAssistancePlugin.settings.get('room_assistance_recipients')
    if not to_list:
        return
    request_start_dt = request.data['start_dt']
    request_data = dict(request.data, start_dt=dateutil.parser.parse(request_start_dt))
    template = get_plugin_template_module('emails/{}.html'.format(template_name), event=request.event,
                                          requested_by=request.created_by_user, request_data=request_data,
                                          **template_params)
    send_email(make_email(from_address=config.NO_REPLY_EMAIL, to_list=to_list, template=template, html=True))


def notify_about_new_request(request):
    send_email_to_assistance(request, template_name='creation_email_to_assistance')


def notify_about_request_modification(request, changes):
    if request.state != RequestState.accepted:
        return
    send_email_to_assistance(request, template_name='modified_request_email_to_assistance', changes=changes)


def notify_about_withdrawn_request(request):
    if request.state != RequestState.withdrawn:
        return
    send_email_to_assistance(request, template_name='withdrawn_email_to_assistance')
