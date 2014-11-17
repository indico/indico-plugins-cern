from __future__ import unicode_literals

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


class CERNUploader(MARCXMLUploader):
    def upload_xml(self, xml):
        pass


class CERNLiveSyncAgent(LiveSyncAgentBase):
    """CERNsearch Agent

    This agent uploads data to CERNsearch.
    """

    uploader = CERNUploader
    form = CERNAgentForm
