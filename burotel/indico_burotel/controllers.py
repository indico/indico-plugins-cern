# This file is part of Indico.
# Copyright (C) 2002 - 2018 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

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
