from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.legacy.webinterface.pages.base import WPDecorated
from indico.legacy.webinterface.wcomponents import WSimpleNavigationDrawer


class WPAudiovisualManagers(WPJinjaMixinPlugin, WPDecorated):
    def _getNavigationDrawer(self):
        return WSimpleNavigationDrawer('Webcast/Recording')

    def _getBody(self, params):
        return self._getPageContent(params)
