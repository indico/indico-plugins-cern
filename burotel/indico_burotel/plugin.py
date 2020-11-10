# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from datetime import datetime, time

from flask import current_app, redirect, request, url_for
from marshmallow import ValidationError, fields
from webargs import dict2schema

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.rb.models.rooms import Room
from indico.modules.rb.schemas import CreateBookingSchema, RoomSchema
from indico.util.marshmallow import NaiveDateTime
from indico.web.flask.util import make_view_func

from indico_burotel.blueprint import blueprint
from indico_burotel.cli import cli
from indico_burotel.controllers import RHLanding, WPBurotelBase


def _add_missing_time(field, data, time_):
    ds = dict2schema({field: fields.Date()})()
    dts = dict2schema({field: NaiveDateTime()})()
    try:
        # let's see if we can load this as a DateTime
        dts.load({field: data[field]})
    except ValidationError:
        # if not, we assume it's a valid date and append the time
        date = ds.load({field: data[field]})[field]
        data[field] = dts.dump({field: datetime.combine(date, time_)})[field]


class BurotelPlugin(IndicoPlugin):
    """Burotel

    Provides burotel-specific functionality
    """

    default_user_settings = {
        'default_experiment': None,
    }

    def init(self):
        super().init()
        current_app.before_request(self._before_request)
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.plugin.get_template_customization_paths, self._override_templates)
        self.connect(signals.plugin.schema_post_dump, self._inject_long_term_attribute, sender=RoomSchema)
        self.connect(signals.plugin.schema_pre_load, self._inject_reason, sender=CreateBookingSchema)
        self.connect(signals.plugin.schema_pre_load, self._inject_time)
        self.inject_bundle('burotel.js', WPBurotelBase)
        self.inject_bundle('burotel.css', WPBurotelBase)

    def get_blueprints(self):
        return blueprint

    def _before_request(self):
        if request.endpoint == 'categories.display':
            return redirect(url_for('rb.roombooking'))
        elif request.endpoint == 'rb.roombooking':
            # render our own landing page instead of the original RH
            return make_view_func(RHLanding)()

    def _extend_indico_cli(self, sender, **kwargs):
        return cli

    def _override_templates(self, sender, **kwargs):
        return os.path.join(self.root_path, 'template_overrides')

    def _inject_long_term_attribute(self, sender, data, **kwargs):
        long_term_room_ids = {room.id for room, value in Room.find_with_attribute('long-term')
                              if value.lower() in ('true', '1', 'yes')}
        for room in data:
            room['is_long_term'] = room['id'] in long_term_room_ids

    def _inject_reason(self, sender, data, **kwargs):
        data.setdefault('reason', 'Burotel booking')

    def _inject_time(self, sender, data, **kwargs):
        if request.blueprint != 'rb':
            return
        if 'start_dt' in data:
            _add_missing_time('start_dt', data, time(0, 0))
        if 'end_dt' in data:
            _add_missing_time('end_dt', data, time(23, 59))
