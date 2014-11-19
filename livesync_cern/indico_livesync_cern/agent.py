from __future__ import unicode_literals

import base64
from urllib import urlencode
from urllib2 import urlopen, Request

from lxml import etree
from wtforms.fields.core import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, URL

from indico.util.i18n import _
from indico.util.string import strip_whitespace
from indico.web.forms.fields import UnsafePasswordField

from indico_livesync import LiveSyncAgentBase, MARCXMLUploader
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
        url = self.agent.agent.settings.get('server_url')
        username = self.agent.agent.settings.get('username')
        password = self.agent.agent.settings.get('password')
        credentials = base64.encodestring('{}:{}'.format(username, password)).strip()
        self.request = Request('{}/ImportXML'.format(url))
        self.request.add_header('Authorization', 'Basic {}'.format(credentials))

    def upload_xml(self, xml):
        result = urlopen(self.request, data=urlencode({'xml': xml}))
        result_text = self._get_result_text(result)
        if not result.code == 200 or not result_text == 'true':
            raise CERNUploaderError('{} - {}'.format(result.code, result_text))

    def _get_result_text(result):
        return etree.tostring(etree.fromstring(result.read()), method="text")


class CERNLiveSyncAgent(LiveSyncAgentBase):
    """CERNsearch Agent

    This agent uploads data to CERNsearch.
    """

    uploader = CERNUploader
    form = CERNAgentForm
