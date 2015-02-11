from __future__ import unicode_literals

from flask import session, render_template
from flask_pluginengine import current_plugin
from wtforms.fields import TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired

from indico.modules.events.requests import RequestFormBase
from indico.web.forms.validators import UsedIf
from indico.web.forms.widgets import JinjaWidget
from indico.web.forms.fields import IndicoSelectMultipleCheckboxField
from indico.util.i18n import _

from indico_requests_audiovisual import SERVICES
from indico_requests_audiovisual.util import is_av_manager, get_contributions


class AVRequestForm(RequestFormBase):
    services = IndicoSelectMultipleCheckboxField(_('Services'), [DataRequired()], choices=SERVICES.items(),
                                                 widget=JinjaWidget('service_type_widget.html', 'requests_audiovisual'),
                                                 description=_("Please choose whether you want a webcast, recording or "
                                                               "both."))
    all_contributions = BooleanField(_('All contributions'),
                                     description=_('Uncheck this if you want to select only certain contributions.'))
    contributions = IndicoSelectMultipleCheckboxField(_('Contributions'),
                                                      [UsedIf(lambda form, field: not form.all_contributions.data),
                                                       DataRequired()])
    webcast_audience = SelectField(_('Webcast Audience'),
                                   description=_("Select the audience to which the webcast will be restricted"))
    comments = TextAreaField(_('Comments'),
                             description=_('If you have any additional comments or instructions, please write them '
                                           'down here.'))

    def __init__(self, *args, **kwargs):
        super(AVRequestForm, self).__init__(*args, **kwargs)
        audiences = [('', _("No restriction - everyone can watch the public webcast"))]
        audiences += sorted((x['audience'], x['audience']) for x in current_plugin.settings.get('webcast_audiences'))
        self.webcast_audience.choices = audiences
        self._update_contribution_fields()

    def _update_contribution_fields(self):
        if self.event.getType() == 'simple_event':
            # lectures don't have contributions
            del self.all_contributions
            del self.contributions
        else:
            self.contributions.choices = list(self._get_contrib_choices())

    def _get_contrib_choices(self):
        is_manager = session.user.isAdmin() or is_av_manager(session.user)
        selected = set(self.request.data.get('contributions', [])) if self.request else set()
        for contrib, capable, custom_room in get_contributions(self.event):
            if not capable and not is_manager and contrib.id not in selected:
                continue
            yield contrib.id, render_template('requests_audiovisual:contrib_selector_entry.html', contrib=contrib,
                                              capable=capable, custom_room=custom_room)
