# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.web.breadcrumbs import render_breadcrumbs
from indico.web.views import WPDecorated

from indico_startup_assistance import _


class WPStartupAssistance(WPJinjaMixinPlugin, WPDecorated):
    def _get_breadcrumbs(self):
        return render_breadcrumbs(_('Startup assistance'))

    def _getBody(self, params):
        return self._getPageContent(params)
