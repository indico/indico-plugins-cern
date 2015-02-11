from __future__ import unicode_literals

from flask import request

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalField, MultipleItemsField, EmailListField

from indico_requests_audiovisual.definition import AVRequest


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
        self.inject_css('requests_audiovisual_css', WPRequestsEventManagement, subclasses=False,
                        condition=lambda: request.view_args.get('type') == AVRequest.name)

    def get_blueprints(self):
        return IndicoPluginBlueprint('requests_audiovisual', 'indico_requests_audiovisual')

    def register_assets(self):
        self.register_css_bundle('requests_audiovisual_css', 'css/requests_audiovisual.scss')

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest
