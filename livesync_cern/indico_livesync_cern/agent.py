from __future__ import unicode_literals

from indico_livesync import LiveSyncAgentBase, MARCXMLUploader


class CERNUploader(MARCXMLUploader):
    def upload_xml(self, xml):
        pass


class CERNLiveSyncAgent(LiveSyncAgentBase):
    """CERNsearch Agent

    This agent uploads data to CERNsearch.
    """

    uploader = CERNUploader
