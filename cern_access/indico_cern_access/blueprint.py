# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_cern_access.controllers import (RHExportCERNAccessCSV, RHExportCERNAccessExcel,
                                            RHRegistrationAccessIdentityData, RHRegistrationEnterIdentityData,
                                            RHRegistrationGrantCERNAccess, RHRegistrationPreviewCERNAccessEmail,
                                            RHRegistrationRevokeCERNAccess, RHStatsAPI)


blueprint = IndicoPluginBlueprint('cern_access', __name__, url_prefix='/event/<int:event_id>')

blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/cern-access/grant',
                       'registrations_grant_cern_access', RHRegistrationGrantCERNAccess, methods=('POST',))
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/cern-access/revoke',
                       'registrations_revoke_cern_access', RHRegistrationRevokeCERNAccess, methods=('POST',))
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/cern-access/email-preview',
                       'registrations_preview_cern_access_email', RHRegistrationPreviewCERNAccessEmail,
                       methods=('POST',))
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/cern-access.csv',
                       'registrations_cern_access_csv', RHExportCERNAccessCSV, defaults={'type': 'cern-access'})
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/cern-access.xlsx',
                       'registrations_cern_access_excel', RHExportCERNAccessExcel, defaults={'type': 'cern-access'})
blueprint.add_url_rule('/manage/registration/<int:reg_form_id>/registrations/<int:registration_id>/cern-access-data',
                       'enter_identity_data', RHRegistrationEnterIdentityData, methods=('GET', 'PUT'))
blueprint.add_url_rule('/registrations/<int:reg_form_id>/access-identity-data', 'access_identity_data',
                       RHRegistrationAccessIdentityData, methods=('GET', 'PUT'))

blueprint.add_url_rule('!/api/plugin/cern-access/visitors', 'api_stats', RHStatsAPI)
