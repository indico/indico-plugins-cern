from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.legacy.webinterface.pages.main import WPMainBase
from indico.legacy.webinterface.wcomponents import WSimpleNavigationDrawer


class WPAccessRequestDetails(WPJinjaMixinPlugin, WPMainBase):
    def _getNavigationDrawer(self):
        return WSimpleNavigationDrawer('CERN Access Request')

    def _getBody(self, params):
        return self._getPageContent(params)
