from __future__ import unicode_literals

from datetime import date
from datetime import timedelta

from flask import session, render_template
from flask_pluginengine import current_plugin
from markupsafe import Markup
from wtforms.ext.dateutil.fields import DateField
from wtforms.fields import TextAreaField, SelectField, BooleanField
from wtforms.fields.html5 import IntegerField, URLField
from wtforms.validators import DataRequired, NumberRange, Optional

from indico.modules.events.requests import RequestFormBase
from indico.modules.events.requests.base import RequestManagerForm
from indico.modules.events.requests.models.requests import RequestState
from indico.web.forms.base import IndicoForm, generated_data
from indico.web.forms.validators import UsedIf, Exclusive
from indico.web.forms.widgets import JinjaWidget
from indico.web.forms.fields import IndicoSelectMultipleCheckboxField, IndicoEnumSelectField
from MaKaC.conference import SubContribution

from indico_audiovisual import SERVICES, _
from indico_audiovisual.util import is_av_manager, get_contributions, contribution_id


class AVRequestForm(RequestFormBase):
    services = IndicoSelectMultipleCheckboxField(_('Services'), [DataRequired()], choices=SERVICES.items(),
                                                 widget=JinjaWidget('service_type_widget.html', 'audiovisual'),
                                                 description=_("Please choose whether you want a webcast, recording or "
                                                               "both."))
    all_contributions = BooleanField(_('All contributions'),
                                     description=_('Uncheck this if you want to select only certain contributions.'))
    contributions = IndicoSelectMultipleCheckboxField(_('Contributions'),
                                                      [UsedIf(lambda form, field: not form.all_contributions.data),
                                                       DataRequired()],
                                                      widget=JinjaWidget('contribution_list_widget.html',
                                                                         'audiovisual',
                                                                         SubContribution=SubContribution))
    webcast_audience = SelectField(_('Webcast Audience'),
                                   description=_("Select the audience to which the webcast will be restricted"))
    comments = TextAreaField(_('Comments'),
                             description=_('If you have any additional comments or instructions, please write them '
                                           'down here.'))

    def __init__(self, *args, **kwargs):
        super(AVRequestForm, self).__init__(*args, **kwargs)
        self._update_audiences()
        self._update_contribution_fields()

    def _update_audiences(self):
        audiences = [('', _("No restriction - everyone can watch the public webcast"))]
        audiences += sorted((x['audience'], x['audience']) for x in current_plugin.settings.get('webcast_audiences'))
        self.webcast_audience.choices = audiences

    def _update_contribution_fields(self):
        if self.event.as_legacy.getType() == 'simple_event':
            # lectures don't have contributions
            del self.all_contributions
            del self.contributions
        else:
            choices = self.contributions.choices = []
            disabled_contribs = self.contributions._disabled_contributions = []
            contributions = self.contributions._contributions = {}
            is_manager = is_av_manager(session.user)
            selected = set(self.request.data.get('contributions', [])) if self.request else set()
            for contrib, capable, custom_room in get_contributions(self.event):
                is_subcontrib = isinstance(contrib, SubContribution)
                id_ = contribution_id(contrib)
                contributions[id_] = contrib
                line = Markup(render_template('audiovisual:contribution_list_entry.html', contrib=contrib,
                                              is_subcontrib=is_subcontrib, capable=capable, custom_room=custom_room))
                if not capable and not is_manager and contrib.id not in selected:
                    disabled_contribs.append((contrib, line))
                else:
                    choices.append((id_, line))


class AVRequestManagerForm(RequestManagerForm):
    custom_webcast_url = URLField(_('Webcast URL'),
                                  description=_("Custom URL to view the webcast. Can contain {event_id} which will be "
                                                "replaced with the ID of this event."))


class RequestListFilterForm(IndicoForm):
    direction = SelectField(_('Sort direction'), [DataRequired()],
                            choices=[('asc', _('Ascending')), ('desc', _('Descending'))])
    granularity = SelectField(_('Granularity'), [DataRequired()],
                              choices=[('events', _('Events')), ('talks', _('Talks'))])
    state = IndicoEnumSelectField(_('Request state'), enum=RequestState, skip={RequestState.withdrawn},
                                  none=_('Any state'))
    abs_start_date = DateField(_('Start Date'), [Optional(), Exclusive('rel_start_date')],
                               parse_kwargs={'dayfirst': True})
    abs_end_date = DateField(_('End Date'), [Optional(), Exclusive('rel_end_date')],
                             parse_kwargs={'dayfirst': True})
    rel_start_date = IntegerField(_('Days in the past'), [Optional(), Exclusive('abs_start_date'), NumberRange(min=0)])
    rel_end_date = IntegerField(_('Days in the future'), [Optional(), Exclusive('abs_end_date'), NumberRange(min=0)])

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
