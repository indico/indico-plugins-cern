from __future__ import unicode_literals

from wtforms.fields import StringField
from wtforms.validators import DataRequired

from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico_livesync_cern import _


class SettingsForm(IndicoForm):
    username = StringField(_("Username"), validators=[DataRequired()],
                           description=_("The username to access the category ID/title mapping"))
    password = IndicoPasswordField(_('Password'), [DataRequired()], toggle=True,
                                   description=_("The password to access the category ID/title mapping"))
