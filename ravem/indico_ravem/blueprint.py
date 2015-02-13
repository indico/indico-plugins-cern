from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_ravem.controllers import RHRavemRoomStatus, RHRavemConnectRoom, RHRavemDisconnectRoom

blueprint = IndicoPluginBlueprint('ravem', 'indico_ravem', url_prefix='/event/<confId>/ravem')

blueprint.add_url_rule('/room-status', RHRavemRoomStatus)
blueprint.add_url_rule('/connect-room', RHRavemConnectRoom, methods=('POST',))
blueprint.add_url_rule('/disconnect-room', RHRavemDisconnectRoom, methods=('POST',))
