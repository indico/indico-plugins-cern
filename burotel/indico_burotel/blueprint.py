# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_burotel.controllers import RHUserExperiment


blueprint = IndicoPluginBlueprint('burotel', __name__, url_prefix='/rooms-new')

blueprint.add_url_rule('/api/user/experiment', 'user_experiment', RHUserExperiment)

# XXX: RHLanding is not handled here on purpose!
