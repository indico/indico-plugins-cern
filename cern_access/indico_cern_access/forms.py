from __future__ import unicode_literals

from markupsafe import Markup

from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.requests import RequestFormBase
from indico.web.forms.fields import IndicoSelectMultipleCheckboxField
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
            .order_by(RegistrationForm.title, RegistrationForm.id)
            .all())
