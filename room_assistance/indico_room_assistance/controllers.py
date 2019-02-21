# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.web.rh import RHProtected

from indico_room_assistance.views import WPRoomAssistance


class RHRequestList(RHProtected):
    """Provides a list of videoconference assistance requests"""

    def _check_access(self):
        RHProtected._check_access(self)

    def _process(self):
        return WPRoomAssistance.render_template('request_list.html')
