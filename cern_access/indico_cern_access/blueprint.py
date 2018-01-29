# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_cern_access.controllers import (RHExportCERNAccessCSV, RHExportCERNAccessExcel,
                                            RHRegistrationAccessIdentityData, RHRegistrationBulkCERNAccess)


blueprint = IndicoPluginBlueprint('cern_access', __name__)
blueprint.add_url_rule('/event/<confId>/manage/registration/<int:reg_form_id>/registrations/cern-access',
                       'registrations_cern_access', RHRegistrationBulkCERNAccess, methods=('POST',))
blueprint.add_url_rule('/event/<confId>/registrations/<int:reg_form_id>/access-identity-data',
                       'access_identity_data', RHRegistrationAccessIdentityData, methods=('GET', 'POST'))
blueprint.add_url_rule('/event/<confId>/manage/registration/<int:reg_form_id>/registrations/cern-access.csv',
                       'registrations_cern_access_csv', RHExportCERNAccessCSV, defaults={'type': 'cern-access'})
blueprint.add_url_rule('/event/<confId>/manage/registration/<int:reg_form_id>/registrations/cern-access.xlsx',
                       'registrations_cern_access_excel', RHExportCERNAccessExcel, defaults={'type': 'cern-access'})
