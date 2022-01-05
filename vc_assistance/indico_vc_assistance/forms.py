# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date, timedelta

from flask import request
from wtforms import SelectField, StringField
from wtforms.fields import IntegerField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional

from indico.modules.events.requests import RequestFormBase
from indico.web.forms.base import IndicoForm, generated_data
from indico.web.forms.fields import IndicoDateField
from indico.web.forms.validators import Exclusive, IndicoRegexp

from indico_vc_assistance import _


class VCAssistanceRequestForm(RequestFormBase):
    comment = TextAreaField(_('Comment'),
                            description=_('If you have any additional comments or instructions, '
                                          'please write them down here.'))


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


class RequestCalendarForm(IndicoForm):
    start_date = StringField(_('From'), [DataRequired(), IndicoRegexp(r'^([+-])?(\d{1,3})d$')],
                             default='-14d',
                             description=_('The offset from the current date, e.g. "-14d"'))
    end_date = StringField(_('To'), [DataRequired(), IndicoRegexp(r'^([+-])?(\d{1,3})d$')],
                           default='14d',
                           description=_('The offset from the current date, e.g. "14d"'))
    alarm = IntegerField(_('Reminder'), [Optional(), NumberRange(min=0)],
                         description=_('Enable a reminder X minutes before the start date'))
