from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_conversion.conversion import RHConversionCheck, RHConversionFinished


blueprint = IndicoPluginBlueprint('conversion', __name__)
blueprint.add_url_rule('/conversion/finished', 'callback', RHConversionFinished, methods=('POST',))
blueprint.add_url_rule('/conversion/check', 'check', RHConversionCheck)
