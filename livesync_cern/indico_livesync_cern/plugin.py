from __future__ import unicode_literals

from indico_livesync import LiveSyncPluginBase

from indico_livesync_cern.agent import LiveSyncCERNAgent


class LiveSyncCERNPlugin(LiveSyncPluginBase):
    """LiveSync CERN

    Provides a CERNsearch agent LiveSync
    """

    agent_classes = {'cernsearch': LiveSyncCERNAgent}
