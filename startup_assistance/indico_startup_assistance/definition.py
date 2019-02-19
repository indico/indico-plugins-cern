# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.modules.events.requests import RequestDefinitionBase

from indico_startup_assistance import _


class StartupAssistanceRequest(RequestDefinitionBase):
    name = 'startup-assistance'
    title = _('Startup assistance')
