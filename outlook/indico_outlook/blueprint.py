from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_outlook.controllers import RHToggleOutlookBlacklist

blueprint = IndicoPluginBlueprint('outlook', 'indico_outlook')

with blueprint.add_prefixed_rules('/user/<int:userId>/preferences', '/user/preferences'):
    blueprint.add_url_rule('/outlook-blacklist', 'toggle_blacklist', RHToggleOutlookBlacklist, methods=('POST',))
