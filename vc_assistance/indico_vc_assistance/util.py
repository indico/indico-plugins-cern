# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.modules.vc import VCRoomEventAssociation


def can_request_assistance(user):
    """Check if a user can request VC assistance"""
    return _is_in_acl(user, 'authorized')


def is_vc_support(user):
    """Check if a user is VC support"""
    return _is_in_acl(user, 'vc_support')


def _is_in_acl(user, acl):
    from indico_vc_assistance.plugin import VCAssistanceRequestPlugin
    if user.is_admin:
        return True
    return VCAssistanceRequestPlugin.settings.acls.contains_user(acl, user)


def has_room_with_vc_attached(event):
    return any(vc for vc in VCRoomEventAssociation.find_for_event(event, include_hidden=True)
               if vc.link_object.room.has_vc)
