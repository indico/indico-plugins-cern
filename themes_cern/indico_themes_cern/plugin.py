# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint


class CERNThemesPlugin(IndicoPlugin):
    """CERN Themes

    Provides event themes for CERN.
    """

    def init(self):
        super().init()
        self.connect(signals.plugin.get_event_themes_files, self._get_themes_yaml)

    def get_blueprints(self):
        return IndicoPluginBlueprint(self.name, __name__)

    def _get_themes_yaml(self, sender, **kwargs):
        return os.path.join(self.root_path, 'themes-cern.yaml')
