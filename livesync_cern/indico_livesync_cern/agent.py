from __future__ import unicode_literals

import requests

from lxml import etree
from wtforms.fields.core import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, URL

from indico.util.i18n import _
from indico.util.string import strip_whitespace
from indico.web.forms.fields import UnsafePasswordField

from indico_livesync import LiveSyncBackendBase, MARCXMLUploader
from indico_livesync import AgentForm


class CERNAgentForm(AgentForm):
    server_url = URLField(_('URL'), [DataRequired(), URL(require_tld=False)], filters=[strip_whitespace],
                          description=_("The URL of CERNsearch's import endpoint"))
    username = StringField(_('Username'), [DataRequired()], filters=[strip_whitespace])
    password = UnsafePasswordField(_('Password'), [DataRequired()], filters=[strip_whitespace])


class CERNUploaderError(Exception):
    pass


class CERNUploader(MARCXMLUploader):
    def __init__(self):
        super(CERNUploader, self).__init__()
        self.url = self.backend.agent.settings.get('server_url')
        self.username = self.backend.agent.settings.get('username')
        self.password = self.backend.agent.settings.get('password')

    def upload_xml(self, xml):
        result = requests.get(self.url, auth=(self.username, self.password), data={'xml': xml})
        result_text = self._get_result_text(result)

        if result.code != 200 or result_text != 'true':
            raise CERNUploaderError('{} - {}'.format(result.code, result_text))

    def _get_result_text(result):
        return etree.tostring(etree.fromstring(result.read()), method="text")


class CERNLiveSyncBackend(LiveSyncBackendBase):
    """CERNsearch

    This backend uploads data to CERNsearch.
    """

    uploader = CERNUploader
    form = CERNAgentForm
