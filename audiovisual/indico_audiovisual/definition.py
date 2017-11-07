# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2017 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask_pluginengine import current_plugin
from markupsafe import Markup, escape
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.exceptions import NotFound

from indico.modules.events.agreements import AgreementDefinitionBase, AgreementPersonInfo
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.util.caching import memoize_request
from indico.util.decorators import classproperty
from indico.util.placeholders import Placeholder
from indico.web.flask.util import url_for

from indico_audiovisual import _
from indico_audiovisual.forms import AVRequestForm, AVRequestManagerForm
from indico_audiovisual.util import (all_agreements_signed, contribution_by_id, contribution_id,
                                     count_capable_contributions, event_has_empty_sessions, get_av_capable_rooms,
                                     get_data_identifiers, get_selected_contributions, get_selected_services,
                                     is_av_manager, send_webcast_ping)


class AVRequest(RequestDefinitionBase):
    name = 'webcast-recording'
    title = _('Webcast / Recording')
    form = AVRequestForm
    manager_form = AVRequestManagerForm
    form_defaults = {'all_contributions': True}
    # needed for templates where we only have access to the definition
    util = {'count_capable_contributions': count_capable_contributions,
            'get_av_capable_rooms': get_av_capable_rooms,
            'event_has_empty_sessions': event_has_empty_sessions,
            'get_selected_contributions': get_selected_contributions,
            'get_selected_services': get_selected_services,
            'all_agreements_signed': all_agreements_signed}

    @classmethod
    def can_be_managed(cls, user):
        return is_av_manager(user)

    @classmethod
    def get_manager_notification_emails(cls):
        return set(current_plugin.settings.get('notification_emails'))

    @classmethod
    def get_notification_template(cls, name, **context):
        context['SubContribution'] = SubContribution
        return super(AVRequest, cls).get_notification_template(name, **context)

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['default_webcast_url'] = cls.plugin.settings.get('webcast_url')
        return super(AVRequest, cls).render_form(event, **kwargs)

    @classmethod
    def create_manager_form(cls, req):
        form = super(AVRequest, cls).create_manager_form(req)
        if 'webcast' not in req.data['services']:
            del form.custom_webcast_url
        return form

    @classmethod
    def send(cls, req, data):
        if (req.id is not None and req.state == RequestState.accepted and
                ('webcast' in req.data['services']) != ('webcast' in data['services'])):
            send_webcast_ping.delay()
        super(AVRequest, cls).send(req, data)
        req.data['identifiers'] = get_data_identifiers(req)
        flag_modified(req, 'data')

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping.delay()
        super(AVRequest, cls).withdraw(req, notify_event_managers)

    @classmethod
    def accept(cls, req, data, user):
        if 'webcast' in req.data['services']:
            send_webcast_ping.delay()
        super(AVRequest, cls).accept(req, data, user)

    @classmethod
    def reject(cls, req, data, user):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping.delay()
        super(AVRequest, cls).reject(req, data, user)

    @classmethod
    def manager_save(cls, req, data):
        super(AVRequest, cls).manager_save(req, data)
        req.data['custom_webcast_url'] = data.get('custom_webcast_url')
        flag_modified(req, 'data')


class SpeakerPersonInfo(AgreementPersonInfo):
    @property
    def identifier(self):
        prefix = '{}-{}'.format(self.email.lower() if self.email else 'NOEMAIL', self.data['type'])
        if self.data['type'] == 'lecture_speaker':
            return '{}:{}'.format(prefix, self.data['person_id'])
        elif self.data['type'] == 'contribution':
            return '{}:{}:{}'.format(prefix, self.data['contribution'], self.data['person_id'])
        else:
            raise ValueError('Unexpected type: {}'.format(self.data['type']))


def _talk_info_from_agreement_data(event, data):
    if data['type'] == 'lecture_speaker':
        return 'lecture', event.url, event.title
    elif data['type'] != 'contribution':
        raise ValueError('Unexpected data type: {}'.format(data['type']))

    obj = contribution_by_id(event, data['contribution'])
    if not obj:
        raise RuntimeError(_('Contribution deleted'))
    if isinstance(obj, SubContribution):
        return 'subcontribution', url_for('contributions.display_subcontribution', obj), obj.title
    else:
        return 'contribution', url_for('contributions.display_contribution', obj), obj.title


class TalkPlaceholder(Placeholder):
    name = 'talk_title'
    required = True
    description = _("The title of the user's talk")

    @classmethod
    def render(cls, definition, agreement):
        return _talk_info_from_agreement_data(agreement.event, agreement.data)[2]


class SpeakerReleaseAgreement(AgreementDefinitionBase):
    name = 'cern-speaker-release'
    title = _('Speaker Release')
    description = _('For talks to be recorded, all involved speakers need to sign the speaker release form.')
    form_template_name = 'agreement_form.html'
    disabled_reason = _('There are no agreements to sign. This means that either no recording request has been '
                        'done/accepted or there are no speakers assigned to the contributions in question.')

    @classmethod
    def can_access_api(cls, user, event):
        return super(SpeakerReleaseAgreement, cls).can_access_api(user, event) or is_av_manager(user)

    @classmethod
    def extend_api_data(cls, event, person, agreement, data):
        data['speaker'] = {'id': person.data['id'],
                           'person_id': person.data['person_id'],
                           'name': person.name,
                           'email': person.email}
        if person.data['type'] == 'lecture_speaker':
            data['contrib'] = unicode(event.id)
        elif person.data['type'] == 'contribution':
            data['contrib'] = person.data['contribution']

    @classproperty
    @classmethod
    @memoize_request
    def paper_form_url(cls):
        return cls.plugin.settings.get('agreement_paper_url')

    @classmethod
    def render_form(cls, agreement, form, **kwargs):
        event = agreement.event
        contrib = None
        is_subcontrib = False
        if agreement.data['type'] == 'contribution':
            talk_type = 'contribution'
            contrib = contribution_by_id(event, agreement.data['contribution'])
            if not contrib:
                raise NotFound
            is_subcontrib = isinstance(contrib, SubContribution)
        elif agreement.data['type'] == 'lecture_speaker':
            talk_type = 'lecture'
        else:
            raise ValueError('Unexpected type: {}'.format(agreement.data['type']))
        kwargs.update({'contrib': contrib,
                       'is_subcontrib': is_subcontrib,
                       'talk_type': talk_type,
                       'event': event})
        return super(SpeakerReleaseAgreement, cls).render_form(agreement, form, **kwargs)

    @classmethod
    def render_data(cls, event, data):
        try:
            type_, url, title = _talk_info_from_agreement_data(event, data)
        except RuntimeError as e:
            return ['({})'.format(e)]
        return [Markup('<a href="{}">{}</a>'.format(url, escape(title)))]

    @classmethod
    def iter_people(cls, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req or req.state != RequestState.accepted or 'recording' not in req.data['services']:
            return
        if event.type == 'lecture':
            for link in event.person_links:
                yield SpeakerPersonInfo(link.full_name, link.email or None,
                                        data={'type': 'lecture_speaker', 'id': link.id, 'person_id': link.person_id})
        else:
            contribs = [x[0] for x in get_selected_contributions(req)]
            for contrib in contribs:
                for link in contrib.person_links:
                    if not link.is_speaker:
                        continue
                    yield SpeakerPersonInfo(link.full_name, link.email or None,
                                            data={'type': 'contribution', 'contribution': contribution_id(contrib),
                                                  'id': link.id, 'person_id': link.person_id})
