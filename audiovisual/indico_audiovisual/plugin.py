# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import g, request, session
from flask_pluginengine import render_plugin_template, url_for_plugin
from sqlalchemy.orm.attributes import flag_modified
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from wtforms.fields.core import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, ValidationError

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import ModelConverter
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.events.requests.views import WPRequestsEventManagement
from indico.modules.rb.models.room_features import RoomFeature
from indico.modules.users import User
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, MultipleItemsField, PrincipalListField
from indico.web.forms.validators import IndicoEmail
from indico.web.http_api import HTTPAPIHook
from indico.web.menu import TopMenuItem

from indico_audiovisual import _
from indico_audiovisual.api import AVExportHook, RecordingLinkAPI
from indico_audiovisual.blueprint import blueprint
from indico_audiovisual.compat import compat_blueprint
from indico_audiovisual.definition import AVRequest, SpeakerReleaseAgreement, TalkPlaceholder
from indico_audiovisual.notifications import notify_relocated_request, notify_rescheduled_request
from indico_audiovisual.util import (compare_data_identifiers, count_capable_contributions, get_data_identifiers,
                                     is_av_manager)
from indico_audiovisual.views import WPAudiovisualManagers


class PluginSettingsForm(IndicoForm):
    managers = PrincipalListField(_('Managers'), groups=True,
                                  description=_('List of users who can manage recording/webcast requests.'))
    notification_emails = EmailListField(_('Notification email addresses'),
                                         description=_('Notifications about recording/webcast requests are sent to '
                                                       'these email addresses (one per line).'))
    notification_reply_email = StringField(_('E-mail notification "reply" address'),
                                           [IndicoEmail()],
                                           description=_('Notifications that are sent to event managers will use '
                                                         'this address in their "Reply-To:" fields.'))
    webcast_audiences = MultipleItemsField(_('Webcast Audiences'),
                                           fields=[{'id': 'audience', 'caption': _('Audience'), 'required': True}],
                                           unique_field='audience',
                                           description=_('List of audiences for non-public webcasts.'))
    webcast_ping_url = URLField(_('Webcast Ping URL'),
                                description=_("A ping is sent via HTTP GET to this URL whenever a webcast request "
                                              "enters/leaves the 'accepted' state."))
    webcast_url = URLField(_('Webcast URL'), [DataRequired()],
                           description=_("The URL to watch the webcast for an event. Can contain {event_id} which "
                                         "will be replaced with the ID of the event."))
    agreement_paper_url = URLField(_('Agreement Paper URL'),
                                   description=_("The URL to the agreement that can be printed and signed offline."))
    recording_cds_url = URLField(_('CDS URL'),
                                 description=_("The URL used when creating recording links. Must contain the {cds_id} "
                                               "placeholder."))
    room_feature = QuerySelectField(_("Room feature"), [DataRequired()], allow_blank=True,
                                    query_factory=lambda: RoomFeature.query, get_label='title',
                                    description=_("The feature indicating that a room supports webcast/recording."))

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
                        'notification_reply_email': '',
                        'notification_emails': [],
                        'webcast_ping_url': '',
                        'webcast_url': '',
                        'agreement_paper_url': None,
                        'recording_cds_url': 'https://cds.cern.ch/record/{cds_id}',
                        'room_feature': None}
    settings_converters = {
        'room_feature': ModelConverter(RoomFeature),
    }
    acl_settings = {'managers'}

    def init(self):
        super(AVRequestsPlugin, self).init()
        self.inject_bundle('main.css', WPAudiovisualManagers)
        self.inject_bundle('main.css', WPRequestsEventManagement, subclasses=False,
                           condition=lambda: request.view_args.get('type') == AVRequest.name)
        self.connect(signals.plugin.get_event_request_definitions, self._get_event_request_definitions)
        self.connect(signals.agreements.get_definitions, self._get_agreement_definitions)
        self.connect(signals.acl.can_access, self._can_access_event, sender=Event)
        self.connect(signals.event.type_changed, self._data_changed)
        self.connect(signals.event.updated, self._event_updated)
        self.connect(signals.event.contribution_updated, self._data_changed)
        self.connect(signals.event.subcontribution_updated, self._data_changed)
        self.connect(signals.event.timetable_entry_updated, self._data_changed)
        self.connect(signals.event.times_changed, self._times_changed, sender=Contribution)
        self.connect(signals.event.times_changed, self._times_changed, sender=Event)
        self.connect(signals.after_process, self._apply_changes)
        self.connect(signals.menu.items, self._extend_top_menu, sender='top-menu')
        self.connect(signals.users.merged, self._merge_users)
        self.connect(signals.get_placeholders, self._get_placeholders, sender='agreement-email')
        self.template_hook('event-header', self._inject_event_header)
        self.template_hook('conference-header-subtitle', self._inject_conference_header_subtitle)
        HTTPAPIHook.register(AVExportHook)
        HTTPAPIHook.register(RecordingLinkAPI)

    def get_blueprints(self):
        yield blueprint
        yield compat_blueprint

    def _get_event_request_definitions(self, sender, **kwargs):
        return AVRequest

    def _get_agreement_definitions(self, sender, **kwargs):
        return SpeakerReleaseAgreement

    def _can_access_event(self, sender, user, **kwargs):
        if user is not None and is_av_manager(user):
            return True

    def _event_updated(self, event, changes, **kwargs):
        if 'venue_room' in changes:
            self._register_event_change(event)

    def _data_changed(self, sender, **kwargs):
        self._register_event_change(sender.event)

    def _times_changed(self, sender, obj, **kwargs):
        self._register_event_change(obj.event)

    def _register_event_change(self, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req:
            return
        g.setdefault('av_request_changes', set()).add(req)

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
                    janitor = User.get_system_user()
                    data = dict(req.data, comment=render_plugin_template('auto_reject_no_capable_contribs.txt'))
                    req.definition.reject(req, data, janitor)
                elif req.state == RequestState.accepted:
                    notify_relocated_request(req)
            req.data['identifiers'] = identifiers
            flag_modified(req, 'data')

    def _get_event_webcast_url(self, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req or req.state != RequestState.accepted or 'webcast' not in req.data['services']:
            return None
        if req.data.get('webcast_hidden'):
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

    def _extend_top_menu(self, sender, **kwargs):
        if not session.user or not is_av_manager(session.user):
            return
        return TopMenuItem('services-cern-audiovisual', _('Webcast/Recording'),
                           url_for_plugin('audiovisual.request_list'), section='services')

    def _merge_users(self, target, source, **kwargs):
        self.settings.acls.merge_users(target, source)

    def _get_placeholders(self, sender, definition, agreement, **kwargs):
        if definition is SpeakerReleaseAgreement:
            return TalkPlaceholder
