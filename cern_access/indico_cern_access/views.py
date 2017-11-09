# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.views import WPConferenceDisplayBase, WPSimpleEventDisplayBase


class WPAccessRequestDetailsConference(WPConferenceDisplayBase, WPJinjaMixinPlugin):
    sidemenu_option = 'registration'

    def _getBody(self, params):
        return WPConferenceDisplayBase._getPageContent(self, params)


class WPAccessRequestDetailsSimpleEvent(WPSimpleEventDisplayBase, WPJinjaMixinPlugin):
    def _getBody(self, params):
        return self._getPageContent(params)
