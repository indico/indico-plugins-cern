# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import os

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint


class LCAgendaThemesPlugin(IndicoPlugin):
    """LCAgenda Themes

    Provides event themes for LCAgenda.
    """

    def init(self):
        super(IndicoPlugin, self).init()
        self.connect(signals.plugin.get_event_themes_files, self._get_themes_yaml)

    def get_blueprints(self):
        return IndicoPluginBlueprint(self.name, __name__)

    def _get_themes_yaml(self, sender, **kwargs):
        return os.path.join(self.root_path, 'themes-lcagenda.yaml')
