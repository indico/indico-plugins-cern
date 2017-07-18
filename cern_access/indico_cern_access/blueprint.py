from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_cern_access.controllers import RHCernAccessRequestsDetails


blueprint = IndicoPluginBlueprint('cern_access', __name__, url_prefix='/service/cern-access')
blueprint.add_url_rule('/<confId>/<int:reg_form_id>', 'access_requests_details', RHCernAccessRequestsDetails, methods=['GET'])
