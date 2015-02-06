from wtforms.fields.simple import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core.plugins import IndicoPlugin, PluginCategory
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import UnsafePasswordField


class SettingsForm(IndicoForm):  # pragma: no cover
    api_endpoint = URLField(_('API endpoint'), [DataRequired()], filters=[lambda x: x.rstrip('/') + '/'],
                            description=_('The endpoint for the RAVEM API'))
    username = StringField(_('Username'), [DataRequired()],
                           description=_('The username used to connect to the RAVEM API'))
    password = UnsafePasswordField(_('Password'), [DataRequired()],
                                   description=_('The password used to connect to the RAVEM API'))


class RavemPlugin(IndicoPlugin):
    """RAVEM

    Manages connections to Vidyo rooms from Indico through the RAVEM api
    """
    configurable = True
    strict_settings = True
    settings_form = SettingsForm
    default_settings = {
        'api_endpoint': 'https://ravem.cern.ch/api/services',
        'username': 'ravem',
        'password': None
    }
    category = PluginCategory.video_conference
