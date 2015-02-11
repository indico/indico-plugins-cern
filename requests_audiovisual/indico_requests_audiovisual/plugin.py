from __future__ import unicode_literals

from flask import request
from flask_pluginengine import render_plugin_template
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin, IndicoPluginBlueprint
from indico.modules.events.requests.models.requests import Request, RequestState
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
    webcast_ping_url = URLField(_('Webcast Ping URL'),
                                description=_("A ping is sent via HTTP GET to this URL whenever a webcast request "
                                              "enters/leaves the 'accepted' state."))
    webcast_url = URLField(_('Webcast URL'), [DataRequired()],
                           description=_("The URL to watch the webcast for an event. Can contain {event_id} which "
                                         "will be replaced with the ID of the event."))
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
                        'notification_emails': [],
                        'webcast_ping_url': None,
                        'webcast_url': ''}
    strict_settings = True

    def init(self):
        super(AVRequestsPlugin, self).init()
        self.inject_css('requests_audiovisual_css', WPRequestsEventManagement, subclasses=False,
                        condition=lambda: request.view_args.get('type') == AVRequest.name)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.template_hook('event-header', self._inject_event_header)
        self.template_hook('conference-header-subtitle', self._inject_conference_header_subtitle)

    def get_blueprints(self):
        return IndicoPluginBlueprint('requests_audiovisual', 'indico_requests_audiovisual')

    def register_assets(self):
        self.register_css_bundle('requests_audiovisual_css', 'css/requests_audiovisual.scss')

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest

    def _get_event_webcast_url(self, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req or req.state != RequestState.accepted or 'webcast' not in req.data['services']:
            return None
        try:
            return self.settings.get('webcast_url').format(event_id=event.id)
        except Exception:
            self.logger.exception('Could not build webcast URL')
            return None

    def _inject_event_header(self, event, **kwargs):
        url = self._get_event_webcast_url(event)
        if not url:
            return
        return render_plugin_template('event_header.html', url=url)

    def _inject_conference_header_subtitle(self, event, **kwargs):
        url = self._get_event_webcast_url(event)
        if not url:
            return
        return render_plugin_template('conference_header.html', url=url)
