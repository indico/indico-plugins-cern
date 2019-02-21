# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_startup_assistance.controllers import RHRequestList


blueprint = IndicoPluginBlueprint('startup_assistance', __name__, url_prefix='/service/startup-assistance')
blueprint.add_url_rule('/', 'request_list', RHRequestList)
