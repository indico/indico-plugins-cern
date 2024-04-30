# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_i18n_demo.controllers import RHCloneEvent


blueprint = IndicoPluginBlueprint('i18n_demo', __name__, url_prefix='/i18n-demo')

blueprint.add_url_rule('/event/<int:event_id>/clone', 'clone_event', RHCloneEvent, methods=('POST',))
