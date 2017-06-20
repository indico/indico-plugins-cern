from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

blueprint = IndicoPluginBlueprint('cern_access', __name__, url_prefix='/service/cern_access')
