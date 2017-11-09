# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from datetime import datetime
from operator import itemgetter

from wtforms.fields import SelectField, StringField
from wtforms.validators import DataRequired, ValidationError

from indico.core.db import db
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.requests import RequestFormBase
from indico.util.countries import get_countries
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoDateField, IndicoSelectMultipleCheckboxField
from indico.web.forms.widgets import JinjaWidget

from indico_cern_access import _


class CERNAccessForm(RequestFormBase):
    regforms = IndicoSelectMultipleCheckboxField(_('Registration forms'),
                                                 widget=JinjaWidget('regform_list_widget.html', 'cern_access'))

    def __init__(self, *args, **kwargs):
        super(CERNAccessForm, self).__init__(*args, **kwargs)
        self.regforms.choices = [(unicode(rf.id), rf.title) for rf in get_regforms(self.event)]


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
