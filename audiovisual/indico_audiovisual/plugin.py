from __future__ import unicode_literals

from flask import request, g, session
from flask_pluginengine import render_plugin_template, url_for_plugin
from sqlalchemy.orm.attributes import flag_modified
from wtforms.fields.core import BooleanField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, ValidationError

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.config import Config
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.modules.users import User
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalListField, MultipleItemsField, EmailListField
from indico.web.http_api import HTTPAPIHook
from indico.web.menu import HeaderMenuEntry

from indico_audiovisual import _
from indico_audiovisual.api import AVExportHook, RecordingLinkAPI
from indico_audiovisual.blueprint import blueprint
from indico_audiovisual.definition import AVRequest, SpeakerReleaseAgreement
from indico_audiovisual.notifications import notify_relocated_request, notify_rescheduled_request
from indico_audiovisual.compat import compat_blueprint
from indico_audiovisual.util import (get_data_identifiers, compare_data_identifiers, is_av_manager,
                                     count_capable_contributions)
from indico_audiovisual.views import WPAudiovisualManagers


class PluginSettingsForm(IndicoForm):
    managers = PrincipalListField(_('Managers'), groups=True, serializable=False,
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
    allow_subcontributions = BooleanField(_('Allow subcontributions'),
                                          description=_('Enables subcontributions to be selected in a '
                                                        'recording/webcast request. Note that selected '
                                                        'subcontributions will be lost when a request is modified '
                                                        'after disabling this setting.'))
    agreement_ping_url = URLField(_('Agreement Ping URL'),
                                  description=_("A ping is sent via HTTP POST to this URL whenever an agreement is "
                                                "signed."))
    agreement_paper_url = URLField(_('Agreement Paper URL'),
                                   description=_("The URL to the agreement that can be printed and signed offline."))
    recording_cds_url = URLField(_('CDS URL'),
                                 description=_("The URL used when creating recording links. Must contain the {cds_id} "
                                               "placeholder."))

    def validate_recording_cds_url(self, field):
        if field.data and '{cds_id}' not in field.data:
            raise ValidationError('{cds_id} placeholder is missing')


class AVRequestsPlugin(IndicoPlugin):
    """Webcast & Recording Request

    Provides a service request where event managers can ask for their
    event to be recorded or webcast.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {'webcast_audiences': [],
                        'notification_emails': [],
                        'webcast_ping_url': None,
                        'webcast_url': '',
                        'allow_subcontributions': False,
                        'agreement_ping_url': None,
                        'agreement_paper_url': None,
                        'recording_cds_url': 'https://cds.cern.ch/record/{cds_id}'}
    acl_settings = {'managers'}
    strict_settings = True

    def init(self):
        super(AVRequestsPlugin, self).init()
        self.inject_css('audiovisual_css', WPAudiovisualManagers)
        self.inject_css('audiovisual_css', WPRequestsEventManagement, subclasses=False,
                        condition=lambda: request.view_args.get('type') == AVRequest.name)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.agreements.get_definitions, self._get_agreement_definitions)
        self.connect(signals.event.data_changed, self._data_changed)
        self.connect(signals.event.has_read_access, self._has_read_access_event)
        self.connect(signals.event.contribution_data_changed, self._data_changed)
        self.connect(signals.event.subcontribution_data_changed, self._data_changed)
        self.connect(signals.after_process, self._apply_changes)
        self.connect(signals.before_retry, self._clear_changes)
        self.connect(signals.indico_menu, self._extend_indico_menu)
        self.connect(signals.users.merged, self._merge_users)
        self.template_hook('event-header', self._inject_event_header)
        self.template_hook('conference-header-subtitle', self._inject_conference_header_subtitle)
        HTTPAPIHook.register(AVExportHook)
        HTTPAPIHook.register(RecordingLinkAPI)

    def get_blueprints(self):
        yield blueprint
        yield compat_blueprint

    def register_assets(self):
        self.register_css_bundle('audiovisual_css', 'css/audiovisual.scss')

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest

    def _get_agreement_definitions(self, sender, **kwargs):
        return SpeakerReleaseAgreement

    def _has_read_access_event(self, sender, user, **kwargs):
        return user is not None and is_av_manager(user)

    def _data_changed(self, sender, **kwargs):
        # sender can be `Conference`, `Contribution` or `SubContribution`
        event = sender.getConference()
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req:
            return
        if 'av_request_changes' not in g:
            g.av_request_changes = set()
        g.av_request_changes.add(req)

    def _apply_changes(self, sender, **kwargs):
        # we are using after_request to avoid spam in case someone changes many contribution times
        if 'av_request_changes' not in g:
            return
        for req in g.av_request_changes:
            identifiers = get_data_identifiers(req)

            if req.state == RequestState.accepted and identifiers['dates'][0] != req.data['identifiers']['dates'][0]:
                notify_rescheduled_request(req)

            if not compare_data_identifiers(identifiers['locations'], req.data['identifiers']['locations']):
                if (not count_capable_contributions(req.event)[0] and
                        req.state in {RequestState.accepted, RequestState.pending} and
                        not is_av_manager(req.created_by_user)):
                    janitor = User.get(int(Config.getInstance().getJanitorUserId()))
                    data = dict(req.data, comment=render_plugin_template('auto_reject_no_capable_contribs.txt'))
                    req.definition.reject(req, data, janitor)
                elif req.state == RequestState.accepted:
                    notify_relocated_request(req)
            req.data['identifiers'] = identifiers
            flag_modified(req, 'data')

    def _clear_changes(self, sender, **kwargs):
        if 'av_request_changes' not in g:
            return
        del g.av_request_changes

    def _get_event_webcast_url(self, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req or req.state != RequestState.accepted or 'webcast' not in req.data['services']:
            return None
        url = req.data.get('custom_webcast_url') or self.settings.get('webcast_url')
        try:
            return url.format(event_id=event.id)
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

    def _extend_indico_menu(self, sender, **kwargs):
        if not session.user or not is_av_manager(session.user):
            return
        return HeaderMenuEntry(url_for_plugin('audiovisual.request_list'), _('Webcast/Recording'), _('Services'))

    def _merge_users(self, target, source, **kwargs):
        self.settings.acls.merge_users(target, source)
