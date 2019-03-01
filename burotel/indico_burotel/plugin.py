# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import os
from datetime import datetime, time

from flask import current_app, json, redirect, request, url_for
from marshmallow import Schema, fields
from werkzeug.datastructures import ImmutableMultiDict

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.util.marshmallow import NaiveDateTime
from indico.web.flask.util import make_view_func

from indico_burotel.blueprint import blueprint
from indico_burotel.controllers import RHLanding, WPBurotelBase


class DateSchema(Schema):
    start_dt = fields.Date()
    end_dt = fields.Date()

    class Meta:
        strict = True  # TODO: remove with marshmallow 3


class DateTimeSchema(Schema):
    start_dt = NaiveDateTime()
    end_dt = NaiveDateTime()

    class Meta:
        strict = True  # TODO: remove with marshmallow 3


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

    default_user_settings = {
        'default_experiment': None,
    }

    def init(self):
        super(BurotelPlugin, self).init()
        current_app.before_request(self._before_request)
        self.connect(signals.plugin.get_template_customization_paths, self._override_templates)
        self.inject_bundle('react.js', WPBurotelBase)
        self.inject_bundle('react.css', WPBurotelBase)
        self.inject_bundle('semantic-ui.js', WPBurotelBase)
        self.inject_bundle('semantic-ui.css', WPBurotelBase)
        self.inject_bundle('burotel.js', WPBurotelBase)
        self.inject_bundle('burotel.css', WPBurotelBase)

    def get_blueprints(self):
        return blueprint

    def _before_request(self):
        if request.endpoint == 'categories.display':
            return redirect(url_for('rooms_new.roombooking'))
        elif request.endpoint == 'rooms_new.roombooking':
            # render our own landing page instead of the original RH
            return make_view_func(RHLanding)()

        # convert dates to datetimes
        if request.blueprint == 'rooms_new':
            if 'start_dt' in request.args:
                request.args = ImmutableMultiDict(patch_time(request.args.to_dict()))
            if request.json and 'start_dt' in request.json:
                data = patch_time(request.json)
                request.data = request._cached_data = json.dumps(data)
                request._cached_json = data

        if request.endpoint == 'rooms_new.create_booking':
            # inject default booking reason if there's none
            if 'reason' not in request.json:
                request._cached_json['reason'] = 'Burotel booking'
                request.data = request._cached_data = json.dumps(request._cached_json)

    def _override_templates(self, sender, **kwargs):
        return os.path.join(self.root_path, 'template_overrides')
