from __future__ import unicode_literals

from indico.core.plugins import url_for_plugin, WPJinjaMixinPlugin
from MaKaC.webinterface.pages.main import WPMainBase
from MaKaC.webinterface.wcomponents import WSimpleNavigationDrawer


class WPAudiovisualManagers(WPJinjaMixinPlugin, WPMainBase):
    def _getNavigationDrawer(self):
        return WSimpleNavigationDrawer('Webcast/Recording', lambda: url_for_plugin('.request_list'))

    def _getBody(self, params):
        return self._getPageContent(params)
