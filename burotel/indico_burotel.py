# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import current_app, redirect, request

from indico.core.plugins import IndicoPlugin
from indico.web.flask.util import url_for


class BurotelPlugin(IndicoPlugin):
    """Burotel

    Provides burotel-specific functionality
    """

    def init(self):
        super(BurotelPlugin, self).init()
        current_app.before_request(self._before_request)

    def _before_request(self):
        if request.endpoint == 'categories.display':
            return redirect(url_for('rooms.roomBooking'))
