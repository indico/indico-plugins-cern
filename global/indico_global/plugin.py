# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPlugin
from indico.web.forms.base import IndicoForm

from indico_global.blueprint import blueprint


class PluginSettingsForm(IndicoForm):
    pass


class GlobalPlugin(IndicoPlugin):
    """Indico Global

    Provides functionality for Indico Global.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {}

    def init(self):
        super().init()
        # TODO add stuff

    def get_blueprints(self):
        return blueprint
