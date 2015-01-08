from __future__ import unicode_literals

from indico_livesync import LiveSyncPluginBase

from indico_livesync_cern.backend import CERNLiveSyncBackend


class CERNLiveSyncPlugin(LiveSyncPluginBase):
    """LiveSync CERN

    Provides the CERNsearch backend for LiveSync
    """

    backend_classes = {'cernsearch': CERNLiveSyncBackend}
    category = 'synchronization'
