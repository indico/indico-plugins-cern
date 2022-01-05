# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date, datetime, time, timedelta

import dateutil.parser
import pytz
from flask import request
from wtforms import SelectField
from wtforms.fields import IntegerField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError

from indico.core.config import config
from indico.modules.events.requests import RequestFormBase
from indico.web.forms.base import IndicoForm, generated_data
from indico.web.forms.fields import IndicoDateField, JSONField
from indico.web.forms.validators import Exclusive
from indico.web.forms.widgets import JinjaWidget

from indico_room_assistance import _


WORKING_TIME_PERIOD = (time(8, 30), time(17, 30))


class _RequestOccurrencesField(JSONField):
    widget = JinjaWidget('assistance_request_occurrences.html', 'room_assistance', single_line=True)

    def process_formdata(self, valuelist):
        super().process_formdata(valuelist)

        dts = []
        tzinfo = pytz.timezone(config.DEFAULT_TIMEZONE)
        for req_date, req_time in self.data.items():
            if not req_time:
                dt = datetime.strptime(req_date, '%Y-%m-%d').date()
            else:
                dt = tzinfo.localize(dateutil.parser.parse(f'{req_date} {req_time}'))
            dts.append(dt)
        self.data = dts

    def _value(self):
        if not self.data:
            return {}

        data = {}
        for dt in self.data:
            if type(dt) is datetime:
                data[dt.date().isoformat()] = dt.strftime('%H:%M')
            elif type(dt) is date:
                data[dt.isoformat()] = None
        return data

    @property
    def event_start_dt(self):
        return self.event.start_dt.astimezone(pytz.timezone(config.DEFAULT_TIMEZONE))


class RoomAssistanceRequestForm(RequestFormBase):
    occurrences = _RequestOccurrencesField(_('When'), [DataRequired()],
                                           description=_('When do you need the assistance?'))
    reason = TextAreaField(_('Reason'), [DataRequired()], description=_('Why are you requesting assistance?'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.occurrences.event = kwargs['event']

    def validate_occurrences(self, field):
        for req_dt in field.data:
            if not isinstance(req_dt, datetime):
                raise ValidationError(_('You have to explicitly specify the time for the assistance request'))
            is_in_working_hours = WORKING_TIME_PERIOD[0] <= req_dt.time() <= WORKING_TIME_PERIOD[1]
            if not is_in_working_hours:
                raise ValidationError(_('One of the specified times is not within the working hours'))


class RequestListFilterForm(IndicoForm):
    direction = SelectField(_('Sort direction'), [DataRequired()],
                            choices=[('asc', _('Ascending')), ('desc', _('Descending'))])
    abs_start_date = IndicoDateField(_('Start Date'), [Optional(), Exclusive('rel_start_date')])
    abs_end_date = IndicoDateField(_('End Date'), [Optional(), Exclusive('rel_end_date')])
    rel_start_date = IntegerField(_('Days in the past'), [Optional(), Exclusive('abs_start_date'), NumberRange(min=0)])
    rel_end_date = IntegerField(_('Days in the future'), [Optional(), Exclusive('abs_end_date'), NumberRange(min=0)])

    def is_submitted(self):
        return bool(request.args)

    @generated_data
    def start_date(self):
        if self.abs_start_date.data is None and self.rel_start_date.data is None:
            return None
        return self.abs_start_date.data or (date.today() - timedelta(days=self.rel_start_date.data))

    @generated_data
    def end_date(self):
        if self.abs_end_date.data is None and self.rel_end_date.data is None:
            return None
        return self.abs_end_date.data or (date.today() + timedelta(days=self.rel_end_date.data))
