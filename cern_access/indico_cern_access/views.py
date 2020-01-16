# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.views import WPSimpleEventDisplayBase


class WPAccessRequestDetails(WPSimpleEventDisplayBase, WPJinjaMixinPlugin):
    def _get_body(self, params):
        return self._get_page_content(params)
