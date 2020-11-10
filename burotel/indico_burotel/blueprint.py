# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.


from indico.core.plugins import IndicoPluginBlueprint

from indico_burotel.controllers import RHBurotelStats, RHBurotelStatsCSV, RHUserExperiment


blueprint = IndicoPluginBlueprint('burotel', __name__, url_prefix='/rooms')

blueprint.add_url_rule('/api/user/experiment', 'user_experiment', RHUserExperiment, methods=('GET', 'POST'))
blueprint.add_url_rule('/api/burotel-stats', 'stats', RHBurotelStats)
blueprint.add_url_rule('/burotel-stats.csv', 'stats_csv', RHBurotelStatsCSV)


# XXX: RHLanding is not handled here on purpose!
