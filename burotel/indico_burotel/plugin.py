# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from datetime import datetime, time

from flask import after_this_request, current_app, has_request_context, redirect, request, url_for
from marshmallow import Schema, ValidationError, fields
from wtforms.fields import SelectField, StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import URL, DataRequired

from indico.core import signals
from indico.core.auth import multipass
from indico.core.plugins import IndicoPlugin
from indico.modules.rb.models.reservations import ReservationState
from indico.modules.rb.models.rooms import Room
from indico.modules.rb.schemas import CreateBookingSchema, RoomSchema
from indico.util.date_time import format_date
from indico.util.marshmallow import NaiveDateTime
from indico.web.flask.util import make_view_func
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico.web.util import ExpectedError

from indico_burotel import _
from indico_burotel.blueprint import blueprint
from indico_burotel.cli import cli
from indico_burotel.controllers import RHLanding, WPBurotelBase
from indico_burotel.tasks import update_access_permissions
from indico_burotel.util import query_user_overlapping_bookings


def _add_missing_time(field, data, time_):
    ds = Schema.from_dict({field: fields.Date()})()
    dts = Schema.from_dict({field: NaiveDateTime()})()
    try:
        # let's see if we can load this as a DateTime
        dts.load({field: data[field]})
    except ValidationError:
        # if not, we assume it's a valid date and append the time
        date = ds.load({field: data[field]})[field]
        data[field] = dts.dump({field: datetime.combine(date, time_)})[field]


def _check_update_permissions(booking):
    if booking.room.get_attribute_value('electronic-lock') == 'yes':
        @after_this_request
        def _launch_task(response):
            update_access_permissions.delay(booking)
            return response


def _check_no_parallel_bookings(booking):
    """Ensure that the user has no other bookings in that interval."""
    overlapping = query_user_overlapping_bookings(booking).first()
    if overlapping:
        raise ExpectedError(_("There is a parallel booking for this person in {0}, from {1} to {2}").format(
            overlapping[0].room.full_name,
            format_date(overlapping[0].start_dt),
            format_date(overlapping[0].end_dt)
        ))


class SettingsForm(IndicoForm):
    _fieldsets = [
        (_('ADaMS Sync'), ['adams_service_url', 'adams_username', 'adams_password', 'cern_identity_provider'])
    ]

    adams_service_url = URLField(_('Service URL'), [DataRequired(), URL(require_tld=False)],
                                 description=_('The URL of the ADaMS service. You must use the {action}, {room}, '
                                               '{person_id}, {start_dt} and {end_dt} placeholders.'))
    adams_username = StringField(_('Username'), validators=[DataRequired()],
                                 description=_('The username to access the ADaMS web service'))
    adams_password = IndicoPasswordField(_('Password'), [DataRequired()], toggle=True,
                                         description=_('The password to access the ADaMS web service'))
    cern_identity_provider = SelectField(_('CERN Identity Provider'), validators=[DataRequired()],
                                         choices=[(k, p.title) for k, p in multipass.identity_providers.items()])


class BurotelPlugin(IndicoPlugin):
    """Burotel

    Provides burotel-specific functionality
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'adams_service_url': '',
        'adams_username': '',
        'adams_password': '',
        'cern_identity_provider': ''
    }
    default_user_settings = {
        'default_experiment': None,
    }

    def init(self):
        super().init()
        current_app.before_request(self._before_request)
        self.connect(signals.rb.booking_created, self._booking_created)
        self.connect(signals.rb.booking_state_changed, self._booking_state_changed)
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
        if not has_request_context() or request.blueprint != 'rb':
            return
        if 'start_dt' in data:
            _add_missing_time('start_dt', data, time(0, 0))
        if 'end_dt' in data:
            _add_missing_time('end_dt', data, time(23, 59))

    def _booking_created(self, booking, **kwargs):
        if booking.state == ReservationState.accepted:
            _check_no_parallel_bookings(booking)
            _check_update_permissions(booking)

    def _booking_state_changed(self, booking, **kwargs):
        if booking.state == ReservationState.accepted:
            _check_no_parallel_bookings(booking)
        _check_update_permissions(booking)
