from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_livesync_cern.controllers import RHCategoriesJSON


blueprint = IndicoPluginBlueprint('livesync_cern', __name__)

blueprint.add_url_rule('/livesync/cernsearch/categories.json', 'categories_json', RHCategoriesJSON)
