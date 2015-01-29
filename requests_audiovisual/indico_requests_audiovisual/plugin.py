from __future__ import unicode_literals

from wtforms.fields import TextAreaField, SelectField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint
from indico.modules.events.requests import RequestDefinitionBase
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalField, MultipleItemsField, IndicoSelectMultipleCheckboxField

from indico_requests_audiovisual.util import is_av_manager


class PluginSettingsForm(IndicoForm):
    managers = PrincipalField(_('Managers'), groups=True,
                              description=_('List of users who can manage recording/webcast requests.'))
    webcast_audiences = MultipleItemsField(_('Webcast Audiences'), fields=[('audience', _('Audience'))],
                                           unique_field='audience',
                                           description=_('List of audiences for non-public webcasts.'))
    # TODO: notification settings
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
                        'webcast_audiences': []}
    strict_settings = True

    def init(self):
        super(AVRequestsPlugin, self).init()
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)

    def get_blueprints(self):
        return IndicoPluginBlueprint('requests_audiovisual', 'indico_requests_audiovisual')

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest


class AVRequestForm(IndicoForm):
    services = IndicoSelectMultipleCheckboxField(_('Services'), [DataRequired()],
                                                 choices=[('webcast', _('Webcast')), ('recording', _('Recording'))],
                                                 description=_("Please choose whether you want a webcast, recording or "
                                                               "both."))
    # TODO: contributions
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


class AVRequest(RequestDefinitionBase):
    name = 'cern_audiovisual'
    title = _('Webcast / Recording')
    form = AVRequestForm

    @classmethod
    def can_be_managed(cls, user):
        return user.isAdmin() or is_av_manager(user)
