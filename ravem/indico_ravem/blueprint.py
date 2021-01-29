# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_ravem.controllers import RHRavemConnectRoom, RHRavemDisconnectRoom, RHRavemRoomStatus


blueprint = IndicoPluginBlueprint('ravem', 'indico_ravem', url_prefix='/event/<int:event_id>/videoconference/ravem')

blueprint.add_url_rule('/room-status/<int:event_vc_room_id>/', 'room_status', RHRavemRoomStatus)
blueprint.add_url_rule('/connect-room/<int:event_vc_room_id>/', 'connect_room', RHRavemConnectRoom, methods=('POST',))
blueprint.add_url_rule('/disconnect-room/<int:event_vc_room_id>/', 'disconnect_room', RHRavemDisconnectRoom,
                       methods=('POST',))
