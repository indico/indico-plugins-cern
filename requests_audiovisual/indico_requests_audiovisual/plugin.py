from __future__ import unicode_literals

from flask import session, render_template
from wtforms.fields import TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint
from indico.modules.events.requests import RequestDefinitionBase, RequestFormBase
from indico.util.i18n import _
from indico.web.forms.validators import UsedIf
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import (PrincipalField, MultipleItemsField, IndicoSelectMultipleCheckboxField,
                                     EmailListField)
from indico.web.forms.widgets import JinjaWidget

from indico_requests_audiovisual.util import is_av_manager, get_contributions, get_av_capable_rooms


SERVICES = {'webcast': _('Webcast'), 'recording': _('Recording')}


class PluginSettingsForm(IndicoForm):
    managers = PrincipalField(_('Managers'), groups=True,
                              description=_('List of users who can manage recording/webcast requests.'))
    notification_emails = EmailListField(_('Notification email addresses'),
                                         description=_('Notifications about recording/webcast requests are sent to '
                                                       'these email addresses (one per line).'))
    webcast_audiences = MultipleItemsField(_('Webcast Audiences'), fields=[('audience', _('Audience'))],
                                           unique_field='audience',
                                           description=_('List of audiences for non-public webcasts.'))
    # TODO: ping url when request is accepted
    # TODO: agreement settings


class AVRequestsPlugin(IndicoPlugin):
    """Webcast & Recording Request

    Provides a service request where event managers can ask for their
    event to be recorded or webcast.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {'managers': [],
                        'webcast_audiences': [],
                        'notification_emails': []}
    strict_settings = True

    def init(self):
        super(AVRequestsPlugin, self).init()
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)

    def get_blueprints(self):
        return IndicoPluginBlueprint('requests_audiovisual', 'indico_requests_audiovisual')

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest


class AVRequestForm(RequestFormBase):
    services = IndicoSelectMultipleCheckboxField(_('Services'), [DataRequired()], choices=SERVICES.items(),
                                                 widget=JinjaWidget('service_type_widget.html', AVRequestsPlugin),
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
        audiences += sorted((x['audience'], x['audience']) for x in AVRequestsPlugin.settings.get('webcast_audiences'))
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


class AVRequest(RequestDefinitionBase):
    name = 'webcast-recording'
    title = _('Webcast / Recording')
    form = AVRequestForm
    form_defaults = {'all_contributions': True}

    @classmethod
    def can_be_managed(cls, user):
        return user.isAdmin() or is_av_manager(user)

    @classmethod
    def get_manager_notification_emails(cls):
        return set(AVRequestsPlugin.settings.get('notification_emails'))

    @classmethod
    def get_selected_contributions(cls, req):
        """Gets the selected contributions for a request.

        :return: list of ``(contribution, capable, custom_room)`` tuples
        """
        if req.event.getType() == 'simple_event':
            return []
        contributions = get_contributions(req.event)
        if not req.data.get('all_contributions', True):
            selected = set(req.data['contributions'])
            contributions = [x for x in contributions if x[0].id in selected]
        return contributions

    @classmethod
    def get_selected_services(cls, req):
        """Gets the selected services

        :return: list of service names
        """
        return [SERVICES.get(s, s) for s in req.data['services']]

    @classmethod
    def has_capable_contributions(cls, event):
        """Checks if there are any contributions in AV-capable rooms"""
        if event.getType() == 'simple_event':
            av_capable_rooms = {r.name for r in get_av_capable_rooms()}
            return event.getRoom() and event.getRoom().getName() in av_capable_rooms
        else:
            return any(capable for _, capable, _ in get_contributions(event))

    @classmethod
    def has_any_contributions(cls, event):
        """Checks if there are any contributions in the event"""
        if event.getType() == 'simple_event':
            # a lecture is basically a contribution on its own
            return True
        else:
            return bool(get_contributions(event))
