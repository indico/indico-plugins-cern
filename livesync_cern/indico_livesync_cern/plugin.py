from __future__ import unicode_literals

from indico_livesync import LiveSyncPluginBase

from indico_livesync_cern.agent import CERNLiveSyncAgent


class CERNLiveSyncPlugin(LiveSyncPluginBase):
    """LiveSync CERN

    Provides a CERNsearch agent for LiveSync
    """

    agent_classes = {'cernsearch': CERNLiveSyncAgent}
