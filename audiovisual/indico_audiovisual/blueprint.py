from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_audiovisual.controllers import RHRequestList


blueprint = IndicoPluginBlueprint('audiovisual', __name__, url_prefix='/service/audiovisual')
blueprint.add_url_rule('/', 'request_list', RHRequestList)
