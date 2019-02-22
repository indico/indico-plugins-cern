# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime, time

from marshmallow_enum import EnumField
from webargs import fields
from webargs.flaskparser import use_args

from indico_burotel import _
from indico.modules.rb.controllers import RHRoomBookingBase
from indico.web.views import WPNewBase


class WPBurotelBase(WPNewBase):
    template_prefix = 'rb_new/'
    title = _('Burotel')
    bundles = ('common.js',)


class RHLanding(RHRoomBookingBase):
    def _process(self):
        return WPBurotelBase.display('room_booking.html')
