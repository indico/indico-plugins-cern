# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime, time

from flask import current_app, json, redirect, request
from marshmallow import Schema, fields
from werkzeug.datastructures import ImmutableMultiDict

from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.util.marshmallow import NaiveDateTime

from indico_burotel.controllers import WPBurotelBase


class DateSchema(Schema):
    start_dt = fields.Date()
    end_dt = fields.Date()


class DateTimeSchema(Schema):
    start_dt = NaiveDateTime()
    end_dt = NaiveDateTime()


def patch_time(args):
    """Patch `request.args` to add a time component."""
    dts = DateTimeSchema()
    ds = DateSchema()
    res = {}
    unserialized_args = ds.load(args).data
    res['start_dt'] = datetime.combine(unserialized_args['start_dt'], time(0, 0))
    if 'end_dt' in unserialized_args:
        res['end_dt'] = datetime.combine(unserialized_args['end_dt'], time(23, 59))
    # Replace request args with updated version
    return dict(args, **dts.dump(res).data)


class BurotelPlugin(IndicoPlugin):
    """Burotel

    Provides burotel-specific functionality
    """

    def init(self):
        super(BurotelPlugin, self).init()
        current_app.before_request(self._before_request)
        self.inject_bundle('react.js', WPBurotelBase)
        self.inject_bundle('react.css', WPBurotelBase)
        self.inject_bundle('semantic-ui.js', WPBurotelBase)
        self.inject_bundle('semantic-ui.css', WPBurotelBase)
        self.inject_bundle('burotel.js', WPBurotelBase)
        self.inject_bundle('burotel.css', WPBurotelBase)

    def get_blueprints(self):
        from indico_burotel.blueprint import blueprint
        return blueprint

    def _before_request(self):
        if 'start_dt' in request.args:
            request.args = ImmutableMultiDict(patch_time(request.args.to_dict()))
        if request.json and 'start_dt' in request.json:
            data = patch_time(request.json)
            request.data = json.dumps(data)
            request._cached_json = data
        if request.endpoint in {'categories.display', 'rooms_new.roombooking'}:
            return redirect(url_for_plugin('burotel.landing'))
