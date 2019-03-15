# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals


def is_room_assistance_support(user):
    from indico_room_assistance.plugin import RoomAssistancePlugin
    if user.is_admin:
        return True
    return RoomAssistancePlugin.settings.acls.contains_user('room_assistance_support', user)
