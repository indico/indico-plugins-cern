# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime
from operator import itemgetter

from wtforms.fields import SelectField, StringField
from wtforms.validators import DataRequired, Optional, ValidationError

from indico.core.db import db
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.requests import RequestFormBase
from indico.util.countries import get_countries
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoDateField, IndicoDateTimeField, IndicoSelectMultipleCheckboxField
from indico.web.forms.validators import LinkedDateTime
from indico.web.forms.widgets import JinjaWidget

from indico_cern_access import _


class CERNAccessForm(RequestFormBase):
    regforms = IndicoSelectMultipleCheckboxField(_('Registration forms'),
                                                 [DataRequired(_('At least one registration form has to be selected'))],
                                                 widget=JinjaWidget('regform_list_widget.html', 'cern_access'))
    start_dt_override = IndicoDateTimeField(_('Start date override'), [Optional()],
                                            description=_("If set, CERN access will be granted starting at the "
                                                          "specified date instead of the event's start date"))
    end_dt_override = IndicoDateTimeField(_('End date override'), [Optional(), LinkedDateTime('start_dt_override',
                                                                                              not_equal=True)],
                                          description=_("If set, CERN access will be granted until the specified date "
                                                        "instead of the event's end date"))

    def __init__(self, *args, **kwargs):
        super(CERNAccessForm, self).__init__(*args, **kwargs)
        regforms = get_regforms(self.event)
        self._regform_map = {unicode(rf.id): rf for rf in regforms}
        self.regforms.choices = [(unicode(rf.id), rf.title) for rf in regforms]
        self.start_dt_override.default_time = self.event.start_dt_local.time()
        self.end_dt_override.default_time = self.event.end_dt_local.time()

    def validate_start_dt_override(self, field):
        if bool(self.start_dt_override.data) != bool(self.end_dt_override.data):
            raise ValidationError(_('You need to specify both date overrides or neither of them.'))

    validate_end_dt_override = validate_start_dt_override


def get_regforms(event):
    return (RegistrationForm.query
            .with_parent(event)
            .order_by(db.func.lower(RegistrationForm.title), RegistrationForm.id)
            .all())


class AccessIdentityDataForm(IndicoForm):
    birth_date = IndicoDateField(_('Birth date'), [DataRequired()])
    nationality = SelectField(_('Nationality'), [DataRequired()])
    birth_place = StringField(_('Place of birth'), [DataRequired()])

    def __init__(self, *args, **kwargs):
        super(AccessIdentityDataForm, self).__init__(*args, **kwargs)
        self.nationality.choices = [('', '')] + sorted(get_countries().iteritems(), key=itemgetter(1))

    def validate_birth_date(self, field):
        if field.data > datetime.now().date():
            raise ValidationError(_('The specified date is in the future'))
