from __future__ import unicode_literals

from indico.modules.events.registration.models.forms import RegistrationForm
from wtforms.validators import DataRequired

from indico.modules.events.requests import RequestFormBase
from indico.web.forms.fields import JSONField
from indico.web.forms.widgets import JinjaWidget

from indico_cern_access import _


class CERNAccessField(JSONField):
    CAN_POPULATE = True
    widget = JinjaWidget('regform_list_widget.html', 'cern_access')

    @property
    def event_regforms(self):
        return (RegistrationForm.query
                .with_parent(self.get_form().event)
                .order_by(RegistrationForm.title, RegistrationForm.id)
                .all())

    def _value(self):
        regforms = []

        for regform in self.event_regforms:
            if regform.cern_access_request and regform.cern_access_request.is_active:
                regform_data = {
                    'regform_id': regform.id,
                    'allow_unpaid': regform.cern_access_request.allow_unpaid
                }
                regforms.append(regform_data)
        return {'regforms': regforms}


class CERNAccessForm(RequestFormBase):
    regforms = CERNAccessField(_('Registration forms'), [DataRequired()])
