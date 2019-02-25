# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import jsonify

from indico.util.caching import memoize_redis
from indico.web.rh import RHProtected

from indico_room_assistance.views import WPRoomAssistance


class RHRequestList(RHProtected):
    """Provides a list of videoconference assistance requests"""

    def _process(self):
        return WPRoomAssistance.render_template('request_list.html')


class RHRoomsWithAssistance(RHProtected):
    @memoize_redis(900)
    def _jsonify_rooms_with_assistance(self):
        from indico_room_assistance.plugin import RoomAssistancePlugin
        rooms = RoomAssistancePlugin.settings.get('rooms_with_assistance')
        return jsonify([room.id for room in rooms])

    def _process(self):
        return self._jsonify_rooms_with_assistance()
