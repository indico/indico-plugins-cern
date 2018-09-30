# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime, time

from flask import current_app, redirect, request
from marshmallow import Schema, fields
from webargs.flaskparser import parser
from werkzeug.datastructures import ImmutableMultiDict

from indico.core.plugins import IndicoPlugin
from indico.web.flask.util import url_for
from indico_burotel.controllers import WPBurotelBase


date_args = {
    'start_dt': fields.Date(),
    'end_dt': fields.Date()
}


class DateTimeSchema(Schema):
    start_dt = fields.DateTime()
    end_dt = fields.DateTime()


def patch_time():
    """Patch `request.args` to add a time component."""
    dts = DateTimeSchema()
    args = parser.parse(date_args, request)
    res = {}
    res[u'start_dt'] = datetime.combine(args['start_dt'], time(0, 0))
    if 'end_dt' in args:
        res[u'end_dt'] = datetime.combine(args['end_dt'], time(23, 59))
    data = request.args.to_dict()
    data.update({k: unicode(v) for k, v in dts.dump(res).data.viewitems()})
    # Replate request args with updated version
    request.args = ImmutableMultiDict(data)


class BurotelPlugin(IndicoPlugin):
    """Burotel

    Provides burotel-specific functionality
    """

    def init(self):
        super(BurotelPlugin, self).init()
        current_app.before_request(self._before_request)
        self.inject_bundle('react.js', WPBurotelBase)
        self.inject_bundle('semantic-ui.js', WPBurotelBase)
        self.inject_bundle('semantic-ui.css', WPBurotelBase)
        self.inject_bundle('burotel.js', WPBurotelBase)
        self.inject_bundle('burotel.css', WPBurotelBase)

    def get_blueprints(self):
        from indico_burotel.blueprint import blueprint
        return blueprint

    def _before_request(self):
        if 'start_dt' in request.args:
            patch_time()
        if request.endpoint in {'categories.display', 'rooms_new.roombooking'}:
            return redirect(url_for('plugin_burotel.landing'))
