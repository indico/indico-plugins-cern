from __future__ import unicode_literals

from wtforms.validators import DataRequired

from indico.modules.events.requests import RequestFormBase
from indico.web.forms.fields import JSONField
from indico.web.forms.widgets import JinjaWidget

from indico_cern_access import _
from indico_cern_access.util import get_regforms_with_access_data


class IndicoAccessField(JSONField):
    CAN_POPULATE = True
    widget = JinjaWidget('regform_list_widget.html', 'cern_access')

    @property
    def event_regforms(self):
        return get_regforms_with_access_data(self.get_form().event)

    def _value(self):
        result = {
            'regforms': []
        }
        for regform in self.event_regforms:
            if regform.access_request:
                regform_data = {
                    'regform_id': regform.id,
                    'allow_unpaid': int(regform.access_request.allow_unpaid)
                }
                result['regforms'].append(regform_data)
            result['regforms'].sort(key=lambda x: x['regform_id'])
        return result


class CernAccessForm(RequestFormBase):
    regforms = IndicoAccessField(_('Registration forms'), [DataRequired()])
