# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import jsonify, session
from webargs import fields, validate
from webargs.flaskparser import use_kwargs

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.web.rh import RHProtected
from indico.web.views import WPNewBase

from indico_burotel import _


class WPBurotelBase(WPNewBase):
    template_prefix = 'rb_new/'
    title = _('Burotel')
    bundles = ('common.js',)


class RHLanding(RHRoomBookingBase):
    def _process(self):
        return WPBurotelBase.display('room_booking.html')


class RHUserExperiment(RHProtected):
    def _process_GET(self):
        from indico_burotel.plugin import BurotelPlugin
        return jsonify(value=BurotelPlugin.user_settings.get(session.user, 'default_experiment'))

    @use_kwargs({
        'value': fields.String(validate=validate.OneOf({'ATLAS', 'CMS', 'ALICE'}), allow_none=True)
    })
    def _process_POST(self, value):
        from indico_burotel.plugin import BurotelPlugin
        BurotelPlugin.user_settings.set(session.user, 'default_experiment', value)
