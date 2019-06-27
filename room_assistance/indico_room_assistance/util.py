# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.modules.events.requests.models.requests import RequestState

from indico_room_assistance.definition import RoomAssistanceRequest


def is_room_assistance_support(user):
    from indico_room_assistance.plugin import RoomAssistancePlugin
    if user.is_admin:
        return True
    return RoomAssistancePlugin.settings.acls.contains_user('room_assistance_support', user)


def event_has_room_with_support_attached(event):
    from indico_room_assistance.plugin import RoomAssistancePlugin
    return event.room in RoomAssistancePlugin.settings.get('rooms_with_assistance')


def can_request_assistance_for_event(event):
    has_room_assistance_request = (event.requests
                                   .filter_by(type=RoomAssistanceRequest.name,
                                              state=RequestState.accepted)
                                   .has_rows())
    room_allows_assistance = event_has_room_with_support_attached(event)
    return not event.has_ended and not has_room_assistance_request and room_allows_assistance
