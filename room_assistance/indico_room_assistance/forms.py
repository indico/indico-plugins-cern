# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import date, time, timedelta

from flask import request, session
from wtforms import SelectField
from wtforms.fields.html5 import IntegerField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError

from indico.modules.events.requests import RequestFormBase
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm, generated_data
from indico.web.forms.fields import IndicoDateField, IndicoDateTimeField
from indico.web.forms.validators import DateTimeRange, Exclusive

from indico_room_assistance import _


WORKING_TIME_PERIODS = ((time(8, 30), time(12, 30)), (time(13, 30), time(17, 30)))


class RoomAssistanceRequestForm(RequestFormBase):
    start_dt = IndicoDateTimeField(_('When'), [DataRequired(),
                                               DateTimeRange(earliest=now_utc())],
                                   description=_('When do you need the assistance?'))
    reason = TextAreaField(_('Reason'), [DataRequired()], description=_('Why are you requesting assistance?'))

    def validate_start_dt(self, field):
        localized_time = field.data.astimezone(session.tzinfo).time()
        is_in_working_hours = any(period[0] <= localized_time <= period[1] for period in WORKING_TIME_PERIODS)
        if not is_in_working_hours:
            raise ValidationError('Specified datetime is not within the working hours')


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
