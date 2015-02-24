# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from indico.core.plugins import url_for_plugin, WPJinjaMixinPlugin
from MaKaC.webinterface.pages.main import WPMainBase
from MaKaC.webinterface.wcomponents import WSimpleNavigationDrawer


class WPAudiovisualManagers(WPJinjaMixinPlugin, WPMainBase):
    def _getNavigationDrawer(self):
        return WSimpleNavigationDrawer('Webcast/Recording', lambda: url_for_plugin('.request_list'))

    def _getBody(self, params):
        # ugly :( but WPMainBase doesn't wrap the page with decent margins and a template would be overkill for this
        return '<div class="container">{}</div>'.format(self._getPageContent(params))
