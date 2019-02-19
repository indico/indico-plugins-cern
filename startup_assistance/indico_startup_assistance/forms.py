# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField

from indico_startup_assistance import _


class StartupAssistanceForm(IndicoForm):
    startup_assistance_recipients = EmailListField(_('Recipients'))
