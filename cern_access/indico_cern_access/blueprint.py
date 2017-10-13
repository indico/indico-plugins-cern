from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_cern_access.controllers import RHRegistrationBulkCERNAccess


blueprint = IndicoPluginBlueprint('cern_access', __name__)
blueprint.add_url_rule('/event/<confId>/manage/registration/<int:reg_form_id>/registrations/cern-access',
                       'registrations_cern_access', RHRegistrationBulkCERNAccess, methods=('POST',))
