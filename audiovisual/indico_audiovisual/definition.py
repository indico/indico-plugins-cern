from __future__ import unicode_literals

from flask_pluginengine import current_plugin
from markupsafe import Markup, escape
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.exceptions import NotFound

from indico.modules.events.agreements import AgreementDefinitionBase, AgreementPersonInfo, EmailPlaceholderBase
from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState, Request
from indico.util.caching import memoize_request
from indico.util.decorators import classproperty
from indico.util.i18n import _
from indico.util.string import to_unicode
from indico.web.flask.util import url_for
from MaKaC.conference import SubContribution

from indico_audiovisual.forms import AVRequestForm, AVRequestManagerForm
from indico_audiovisual.util import (is_av_manager, send_webcast_ping, get_data_identifiers, get_selected_contributions,
                                     contribution_id, contribution_by_id, send_agreement_ping,
                                     count_capable_contributions, get_av_capable_rooms, event_has_empty_sessions,
                                     get_selected_services, all_agreements_signed)


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
    def render_form(cls, **kwargs):
        kwargs['default_webcast_url'] = cls.plugin.settings.get('webcast_url')
        return super(AVRequest, cls).render_form(**kwargs)

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
            send_webcast_ping()
        super(AVRequest, cls).send(req, data)
        req.data['identifiers'] = get_data_identifiers(req)
        flag_modified(req, 'data')

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).withdraw(req, notify_event_managers)

    @classmethod
    def accept(cls, req, data, user):
        if 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).accept(req, data, user)

    @classmethod
    def reject(cls, req, data, user):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).reject(req, data, user)

    @classmethod
    def manager_save(cls, req, data):
        super(AVRequest, cls).manager_save(req, data)
        req.data['custom_webcast_url'] = data.get('custom_webcast_url')
        flag_modified(req, 'data')


class SpeakerPersonInfo(AgreementPersonInfo):
    @property
    def identifier(self):
        prefix = '{}-{}'.format(self.email, self.data['type'])
        if self.data['type'] == 'lecture_speaker':
            return '{}:{}'.format(prefix, self.data['speaker_id'])
        elif self.data['type'] == 'contribution':
            return '{}:{}:{}'.format(prefix, self.data['contribution'], self.data['speaker_id'])
        else:
            raise ValueError('Unexpected type: {}'.format(self.data['type']))


def _talk_info_from_agreement_data(event, data):
    if data['type'] == 'lecture_speaker':
        return 'lecture', url_for('event.conferenceDisplay', event), to_unicode(event.getTitle())
    elif data['type'] != 'contribution':
        raise ValueError('Unexpected data type: {}'.format(data['type']))

    contrib_id, _unused, subcontrib_id = data['contribution'].partition('-')
    contrib = event.getContributionById(contrib_id)
    if not contrib:
        raise RuntimeError(_('Contribution deleted'))
    if not subcontrib_id:
        return 'contribution', url_for('event.contributionDisplay', contrib), to_unicode(contrib.getTitle())

    subcontrib = contrib.getSubContributionById(subcontrib_id)
    if not subcontrib:
        raise RuntimeError(_('Subcontribution deleted'))
    return 'subcontribution', url_for('event.subContributionDisplay', subcontrib), to_unicode(subcontrib.getTitle())


class TalkPlaceholder(EmailPlaceholderBase):
    required = True
    description = _("The title of the user's talk")

    @classmethod
    def render(cls, agreement):
        return _talk_info_from_agreement_data(agreement.event, agreement.data)[2]


class SpeakerReleaseAgreement(AgreementDefinitionBase):
    name = 'cern-speaker-release'
    title = _('Speaker Release')
    description = _('For talks to be recorded or webcast, all involved speakers need to sign the speaker release form.')
    form_template_name = 'agreement_form.html'
    email_placeholders = {'talk_title': TalkPlaceholder}

    @classmethod
    def can_access_api(cls, user, event):
        return super(SpeakerReleaseAgreement, cls).can_access_api(user, event) or is_av_manager(user)

    @classmethod
    def extend_api_data(cls, event, person, agreement, data):
        data['confId'] = event.getId()
        data['signed'] = data['accepted']
        data['speaker'] = {'id': person.data['speaker_id'],
                           'name': person.name,
                           'email': person.email}
        if person.data['type'] == 'lecture_speaker':
            data['contrib'] = event.getId()
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
    def handle_accepted(cls, agreement):
        send_agreement_ping(agreement)

    @classmethod
    def handle_rejected(cls, agreement):
        send_agreement_ping(agreement)

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
        if event.getType() == 'simple_event':
            for speaker in event.getChairList():
                if not speaker.getEmail():
                    continue
                yield SpeakerPersonInfo(to_unicode('{} {}'.format(speaker.getFirstName(), speaker.getFamilyName())),
                                        to_unicode(speaker.getEmail()),
                                        data={'type': 'lecture_speaker', 'speaker_id': speaker.getId()})
        else:
            contribs = [x[0] for x in get_selected_contributions(req)]
            for contrib in contribs:
                for speaker in contrib.getSpeakerList():
                    if not speaker.getEmail():
                        continue
                    yield SpeakerPersonInfo(to_unicode(speaker.getDirectFullNameNoTitle(upper=False)),
                                            to_unicode(speaker.getEmail()),
                                            data={'type': 'contribution', 'contribution': contribution_id(contrib),
                                                  'speaker_id': speaker.getId()})
