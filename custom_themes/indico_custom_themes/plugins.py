# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import os

from flask.helpers import get_root_path

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint


class ThemesPluginBase(IndicoPlugin):
    THEME_YAML = None

    def init(self):
        super(ThemesPluginBase, self).init()
        self.connect(signals.plugin.get_event_themes_files, self._get_themes_yaml)

    def get_blueprints(self):
        return IndicoPluginBlueprint(self.name, __name__)

    def _get_themes_yaml(self, sender, **kwargs):
        return os.path.join(get_root_path('indico_custom_themes'), self.THEME_YAML)


class LCAgendaThemesPlugin(ThemesPluginBase):
    """LCAgenda Themes

    Provides event themes for LCAgenda.
    """

    THEME_YAML = 'themes-lcagenda.yaml'


class CERNThemesPlugin(ThemesPluginBase):
    """CERN Themes

    Provides event themes for CERN.
    """

    THEME_YAML = 'themes-cern.yaml'
