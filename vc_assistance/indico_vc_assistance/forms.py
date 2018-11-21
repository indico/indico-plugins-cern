# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from wtforms.fields.simple import TextAreaField

from indico.modules.events.requests import RequestFormBase

from indico_vc_assistance import _


class VCRequestForm(RequestFormBase):
    comment = TextAreaField(_('Comment'),
                            description=_('If you have any additional comments or instructions,'
                                          'please write them down here.'))
