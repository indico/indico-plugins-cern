# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

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
