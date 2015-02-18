from __future__ import unicode_literals

from flask_pluginengine import current_plugin, plugin_context, render_plugin_template
from sqlalchemy.orm.attributes import flag_modified

from indico.modules.agreements.base import AgreementDefinitionBase
from indico.modules.agreements.models.agreements import AgreementPersonInfo
from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState, Request
from indico.util.decorators import classproperty
from indico.util.i18n import _
from MaKaC.conference import SubContribution

from indico_requests_audiovisual import util
from indico_requests_audiovisual.forms import AVRequestForm
from indico_requests_audiovisual.util import (is_av_manager, send_webcast_ping, get_data_identifiers,
                                              get_selected_contributions, contribution_id, contribution_by_id,
                                              send_agreement_ping)


class AVRequest(RequestDefinitionBase):
    name = 'webcast-recording'
    title = _('Webcast / Recording')
    form = AVRequestForm
    form_defaults = {'all_contributions': True}
    util = util  # needed for templates where we only have access to the definition

    @classmethod
    def can_be_managed(cls, user):
        return user.isAdmin() or is_av_manager(user)

    @classmethod
    def get_manager_notification_emails(cls):
        return set(current_plugin.settings.get('notification_emails'))

    @classmethod
    def get_notification_template(cls, name, **context):
        context['SubContribution'] = SubContribution
        return super(AVRequest, cls).get_notification_template(name, **context)

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


class SpeakerReleaseAgreement(AgreementDefinitionBase):
    name = 'webcast-recording-speaker-release'
    title = _('Speaker Release')

    @classproperty
    @classmethod
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
            is_subcontrib = isinstance(contrib, SubContribution)
        elif agreement.data['type'] == 'lecture_speaker':
            talk_type = 'lecture'
        else:
            raise ValueError('Unexpected type: {}'.format(agreement.data['type']))
        with plugin_context(cls.plugin):
            return render_plugin_template('agreement_form.html', agreement=agreement, form=form, contrib=contrib,
                                          is_subcontrib=is_subcontrib, talk_type=talk_type, event=event, **kwargs)

    @classmethod
    def handle_accepted(cls, agreement):
        send_agreement_ping(agreement)

    @classmethod
    def handle_rejected(cls, agreement):
        send_agreement_ping(agreement)

    @classmethod
    def iter_people(cls, event):
        req = Request.find_latest_for_event(event, AVRequest.name)
        if not req or req.state != RequestState.accepted:
            return
        if event.getType() == 'simple_event':
            for speaker in event.getChairList():
                yield AgreementPersonInfo(speaker.getDirectFullNameNoTitle(), speaker.getEmail(),
                                          data={'type': 'lecture_speaker'})
        else:
            contribs = [x[0] for x in get_selected_contributions(req)]
            for contrib in contribs:
                for speaker in contrib.getSpeakerList():
                    yield AgreementPersonInfo(speaker.getDirectFullNameNoTitle(upper=False), speaker.getEmail(),
                                              data={'type': 'contribution', 'contribution': contribution_id(contrib)})
