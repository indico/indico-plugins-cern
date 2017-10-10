from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.web.breadcrumbs import render_breadcrumbs
from indico.web.views import WPDecorated

from indico_audiovisual import _


class WPAudiovisualManagers(WPJinjaMixinPlugin, WPDecorated):
    def _get_breadcrumbs(self):
        return render_breadcrumbs(_('Webcast/Recording'))

    def _getBody(self, params):
        return self._getPageContent(params)
