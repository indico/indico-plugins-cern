# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.modules.events.requests import RequestDefinitionBase

from indico_vc_assistance import _
from indico_vc_assistance.forms import VCRequestForm


class VCRequest(RequestDefinitionBase):
    name = 'vc-assistance'
    title = _('Videconference assistance')
    form = VCRequestForm

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def render_form(cls, event, **kwargs):
        return super(VCRequest, cls).render_form(event, **kwargs)
