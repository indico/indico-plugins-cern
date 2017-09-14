from __future__ import unicode_literals

from indico_livesync import LiveSyncPluginBase
from indico_livesync_cern.backend import CERNLiveSyncBackend
from indico_livesync_cern.blueprint import blueprint
from indico_livesync_cern.forms import SettingsForm


class CERNLiveSyncPlugin(LiveSyncPluginBase):
    """LiveSync CERN

    Provides the CERNsearch backend for LiveSync
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {'username': 'cernsearch', 'password': ''}
    backend_classes = {'cernsearch': CERNLiveSyncBackend}

    def get_blueprints(self):
        return blueprint
