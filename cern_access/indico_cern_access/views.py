from __future__ import unicode_literals

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.views import WPConferenceDisplayBase


class WPAccessRequestDetails(WPJinjaMixinPlugin, WPConferenceDisplayBase):
    sidemenu_option = 'registration'
