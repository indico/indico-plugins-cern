# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import datetime
from operator import itemgetter

from markupsafe import Markup
from wtforms.fields import BooleanField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from indico.core.db import db
from indico.modules.events.registration.forms import EmailRegistrantsForm
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.requests import RequestFormBase
from indico.util.countries import get_countries
from indico.util.placeholders import get_missing_placeholders, render_placeholder_info
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoDateField, IndicoDateTimeField, IndicoSelectMultipleCheckboxField
from indico.web.forms.util import inject_validators
from indico.web.forms.validators import HiddenUnless, IndicoRegexp, LinkedDateTime, UsedIf
from indico.web.forms.widgets import JinjaWidget, SwitchWidget

from indico_cern_access import _
from indico_cern_access.util import sanitize_license_plate


class GrantAccessEmailForm(EmailRegistrantsForm):
    save_default = BooleanField(_("Save as default"), widget=SwitchWidget(),
                                description=_("Save this email's content as the default that will be used the next "
                                              "time a CERN access request is sent for a registrant in this event."))

    def __init__(self, *args, **kwargs):
        reset_text = (Markup('<a id="reset-cern-access-email">{}</a><br>')
                      .format(_('Click here to reset subject and body to the default text.')))
        super().__init__(*args, recipients=[], **kwargs)
        self.body.description = reset_text + render_placeholder_info('cern-access-email', regform=self.regform,
                                                                     registration=None)
        del self.cc_addresses
        del self.copy_for_sender
        del self.attach_ticket
        del self.recipients

    def validate_body(self, field):
        missing = get_missing_placeholders('cern-access-email', field.data, regform=self.regform, registration=None)
        if missing:
            raise ValidationError(_('Missing placeholders: {}').format(', '.join(missing)))


class CERNAccessForm(RequestFormBase):
    regforms = IndicoSelectMultipleCheckboxField(_('Registration forms'),
                                                 [DataRequired(_('At least one registration form has to be selected'))],
                                                 widget=JinjaWidget('regform_list_widget.html', 'cern_access'))
    during_registration = BooleanField(_('Show during user registration'), widget=SwitchWidget(),
                                       description=_("When enabled, users can request site access while registering "
                                                     "and provide their additional personal data in the registration "
                                                     "form. In any case, site access is only granted after a manager "
                                                     "explicitly enables it for the registrants."))
    during_registration_preselected = BooleanField(_('Preselect during user registration'),
                                                   [HiddenUnless('during_registration')], widget=SwitchWidget(),
                                                   description=_("Preselect the option to request site access during "
                                                                 "registration. Recommended if most registrants will "
                                                                 "need it."))
    during_registration_required = BooleanField(_('Require during user registration'),
                                                [HiddenUnless('during_registration_preselected')],
                                                widget=SwitchWidget(),
                                                description=_("Require all users to provide data for site access. "
                                                              "Registration without entering the data will not be "
                                                              "possible."))
    start_dt_override = IndicoDateTimeField(_('Start date override'), [Optional()],
                                            description=_("If set, CERN access will be granted starting at the "
                                                          "specified date instead of the event's start date"))
    end_dt_override = IndicoDateTimeField(_('End date override'), [Optional(), LinkedDateTime('start_dt_override',
                                                                                              not_equal=True)],
                                          description=_("If set, CERN access will be granted until the specified date "
                                                        "instead of the event's end date"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regforms = get_regforms(self.event)
        self._regform_map = {str(rf.id): rf for rf in regforms}
        self.regforms.choices = [(str(rf.id), rf.title) for rf in regforms]
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
    nationality = SelectField(_('Country of birth'), [DataRequired()])
    birth_place = StringField(_('Place of birth'), [DataRequired()])
    by_car = BooleanField(_('Are you bringing your own car?'), [Optional()], widget=SwitchWidget())
    license_plate = StringField(
        _('License plate'),
        [
            HiddenUnless('by_car'),
            Length(min=3),
            IndicoRegexp(r'^[0-9A-Za-z]+([- ][ ]*[0-9A-Za-z]+)*$',
                         message=_('Wrong format. Only letters and numbers separated by dashes (-) or spaces allowed'))
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nationality.choices = [('', '')] + sorted(get_countries().items(), key=itemgetter(1))

    def validate_birth_date(self, field):
        if field.data > datetime.now().date():
            raise ValidationError(_('The specified date is in the future'))

    def validate_license_plate(self, field):
        if self.by_car.data and not sanitize_license_plate(field.data):
            raise ValidationError(_('Please insert a valid license plate number!'))


class RegistrationFormPersonalDataForm(AccessIdentityDataForm):
    request_cern_access = BooleanField(_('Request access to the CERN site'), widget=SwitchWidget())

    @classmethod
    def _add_fields_hidden_unless(cls):
        for field_name in ('birth_date', 'nationality', 'birth_place'):
            inject_validators(RegistrationFormPersonalDataForm, field_name,
                              [UsedIf(lambda form, field: form.request_cern_access.data)], early=True)


RegistrationFormPersonalDataForm._add_fields_hidden_unless()
