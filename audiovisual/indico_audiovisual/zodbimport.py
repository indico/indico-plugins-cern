from __future__ import unicode_literals

import os
import sys
from contextlib import contextmanager

from indico.core.config import Config
from indico.core.db import db
from indico.modules.events.agreements.models.agreements import Agreement, AgreementState
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.util.console import cformat
from indico.util.date_time import now_utc
from indico.util.string import is_valid_mail
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode, convert_principal_list, option_value

from indico_audiovisual.definition import AVRequest, SpeakerReleaseAgreement, SpeakerPersonInfo
from indico_audiovisual.plugin import AVRequestsPlugin
from indico_audiovisual.util import get_data_identifiers


class AVRequestsImporter(Importer):
    plugins = {'audiovisual'}

    def has_data(self):
        return bool(Request.find(type=AVRequest.name).count())

    @contextmanager
    def _monkeypatch(self):
        prop = Request.event
        # By default `Request.event` uses ConferenceHolder which is not available here
        Request.event = property(lambda req: self.zodb_root['conferences'][str(req.event_id)],
                                 prop.fset,
                                 prop.fdel)
        try:
            yield
        finally:
            Request.event = prop

    def migrate(self):
        self.migrate_settings()
        with self._monkeypatch():
            self.migrate_requests()

    def migrate_settings(self):
        print cformat('%{white!}migrating settings')
        AVRequestsPlugin.settings.delete_all()
        plugin_type = self.zodb_root['plugins']['Collaboration']
        wc_opts = plugin_type._PluginType__plugins['WebcastRequest']._PluginBase__options
        rr_opts = plugin_type._PluginType__plugins['RecordingRequest']._PluginBase__options
        AVRequestsPlugin.settings.set('managers', list(set(convert_principal_list(wc_opts['admins'])) |
                                                       set(convert_principal_list(rr_opts['admins']))))
        emails = option_value(wc_opts['additionalEmails']) + option_value(rr_opts['additionalEmails'])
        AVRequestsPlugin.settings.set('notification_emails', list({convert_to_unicode(email)
                                                                   for email in emails
                                                                   if is_valid_mail(email, multi=False)}))
        AVRequestsPlugin.settings.set('webcast_audiences',
                                      sorted([{'audience': convert_to_unicode(x['name'])}
                                              for x in option_value(wc_opts['webcastAudiences'])]))
        AVRequestsPlugin.settings.set('webcast_url', 'http://webcast.web.cern.ch/webcast/play.php?event={event_id}')
        AVRequestsPlugin.settings.set('webcast_ping_url',
                                      convert_to_unicode(self.zodb_root['WebcastManager']._webcastSynchronizationURL))
        wc_form_url = option_value(wc_opts['ConsentFormURL'])
        rr_form_url = option_value(rr_opts['ConsentFormURL'])
        wc_ping_url = option_value(wc_opts['AgreementNotificationURL'])
        rr_ping_url = option_value(rr_opts['AgreementNotificationURL'])
        if wc_form_url and rr_form_url:
            assert wc_form_url == rr_form_url
        if wc_ping_url and rr_ping_url:
            assert wc_ping_url == rr_ping_url
        AVRequestsPlugin.settings.set('agreement_ping_url', wc_ping_url or rr_ping_url)
        AVRequestsPlugin.settings.set('agreement_paper_url', wc_form_url or rr_form_url)
        db.session.commit()

    def migrate_requests(self):
        print cformat('%{white!}migrating requests')
        status_map = {None: RequestState.pending,
                      True: RequestState.accepted,
                      False: RequestState.rejected}
        for csbm in committing_iterator(self._iter_csbms()):
            event = csbm._conf
            if event.id not in self.zodb_root['conferences']:
                print cformat(' - %{yellow}ignored event {} (not in event index)').format(event.id)
                continue
            wc_ids = csbm._bookingsByType.get('WebcastRequest')
            rr_ids = csbm._bookingsByType.get('RecordingRequest')
            assert not wc_ids or len(wc_ids) == 1
            assert not rr_ids or len(rr_ids) == 1
            wc = csbm._bookings[wc_ids[0]] if wc_ids else None
            rr = csbm._bookings[rr_ids[0]] if rr_ids else None
            wc_ignored = rr_ignored = None
            data_source = wc or rr
            if wc and rr and wc._acceptRejectStatus != rr._acceptRejectStatus:
                # First try to get rid of a pending request. If none in pending, get rid of the rejected one.
                for status in (None, False):
                    if wc._acceptRejectStatus == status:
                        data_source = rr
                        wc_ignored = wc
                        wc = None
                        break
                    elif rr._acceptRejectStatus == status:
                        data_source = wc
                        rr_ignored = rr
                        rr = None
                        break
            # Create the new request
            req = Request(event=event, type=AVRequest.name)
            req.state = status_map[data_source._acceptRejectStatus]
            req.created_by_id = int(Config.getInstance().getJanitorUserId())
            req.created_dt = data_source._creationDate
            if req.state == RequestState.rejected:
                req.comment = convert_to_unicode(data_source._rejectReason)
            # Data specific to the request type
            all_contributions = ((wc and wc._bookingParams['talks'] == 'all') or
                                 (rr and rr._bookingParams['talks'] == 'all'))
            contributions = list(set(wc._bookingParams['talkSelection'] if wc else []) |
                                 set(rr._bookingParams['talkSelection'] if rr else []))
            data = {'services': filter(None, ['webcast' if wc else None, 'recording' if rr else None]),
                    'all_contributions': all_contributions,
                    'contributions': contributions if not all_contributions else [],
                    'comments': convert_to_unicode(data_source._bookingParams['otherComments'])}
            if wc:
                data['webcast_audience'] = convert_to_unicode(wc._bookingParams.get('audience', ''))
            req.data = data
            req.data['identifiers'] = get_data_identifiers(req)  # this depends on req.data
            db.session.add(req)
            print cformat(' - %{cyan}event {} ({} - {})').format(event.id, req.state.name,
                                                                 ', '.join(req.data['services']))
            if rr_ignored:
                print cformat('   %{yellow}ignored recording request ({})').format(
                    status_map[rr_ignored._acceptRejectStatus].name)
            if wc_ignored:
                print cformat('   %{yellow}ignored webcast request ({})').format(
                    status_map[wc_ignored._acceptRejectStatus].name)
            self.migrate_agreements(csbm)

    def migrate_agreements(self, csbm):
        # old: NOEMAIL, NOTSIGNED, SIGNED, FROMFILE, PENDING, REFUSED = xrange(6)
        # NOEMAIL was for speakers with no email set (wtf?)
        # NOTSIGNED was for speakers where nothing was set yet
        status_map = [None, None, AgreementState.accepted, AgreementState.accepted_on_behalf,
                      AgreementState.pending, AgreementState.rejected]

        unsent = 0
        has_agreements = False
        for speaker_wrapper in csbm._speakerWrapperList:
            speaker = speaker_wrapper.speaker
            new_status = status_map[speaker_wrapper.status]
            if new_status is None:
                unsent += 1
                continue
            status_name = new_status.name if new_status is not None else '(unsent)'
            print cformat('   %{blue!}agreement for {}: {}').format(speaker._email or '(no email)', status_name)
            if new_status is None:
                print cformat('     %{yellow}skipped unsent agreement')
                continue
            data = {}
            if speaker.__class__.__name__ == 'ContributionParticipation':
                data['type'] = 'contribution'
                data['contribution'] = speaker_wrapper.contId
                data['speaker_id'] = speaker._id
            elif speaker.__class__.__name__ == 'ConferenceChair':
                data['type'] = 'lecture_speaker'
                data['speaker_id'] = speaker._id
            else:
                raise ValueError('Unexpected speaker: {}'.format(speaker.__class__.__name__))
            agreement = Agreement(event=csbm._conf, type=SpeakerReleaseAgreement.name)
            agreement.uuid = speaker_wrapper.uniqueIdHash
            agreement.person_email = convert_to_unicode(speaker._email)
            agreement.person_name = convert_to_unicode('{0._firstName} {0._surName}'.format(speaker))
            agreement.state = new_status
            agreement.signed_dt = speaker_wrapper.dateAgreement or now_utc()
            agreement.signed_from_ip = speaker_wrapper.ipSignature
            agreement.reason = speaker_wrapper.reason
            agreement.data = data
            # no-email-address is terrible but we have a few (~10) speakers without an email.
            # those will never show up in the agreement listing but at least we keep the information
            # that they did sign (on paper) in the database..
            spi = SpeakerPersonInfo(agreement.person_name, agreement.person_email or 'no-email-address',
                                    data=agreement.data)
            agreement.identifier = spi.identifier
            if new_status == AgreementState.accepted_on_behalf:
                filename, path = self._get_file_data(speaker_wrapper.localFile)
                if not path:
                    print cformat('     %{red!}uploaded file not found')
                    # XXX: should we set status to `accepted` instead to avoid broken links?
                else:
                    agreement.attachment_filename = filename
                    with open(path, 'rb') as f:
                        agreement.attachment = f.read()
                    print cformat('     %{grey!}attachment: {} ({} bytes)').format(filename,
                                                                                   len(agreement.attachment_filename))
            db.session.add(agreement)
            has_agreements = True

        if has_agreements:
            enabled = bool(getattr(csbm, '_notifyElectronicAgreementAnswer', True))
            SpeakerReleaseAgreement.event_settings.set(csbm._conf, 'manager_notifications_enabled', enabled)

        if unsent:
            print cformat('   %{yellow}skipped {} unsent agreements').format(unsent)

    def _get_file_data(self, f):
        # this is based pretty much on MaterialLocalRepository.__getFilePath, but we don't
        # call any legacy methods in ZODB migrations to avoid breakage in the future.
        archive_path = Config.getInstance().getArchiveDir()
        archive_id = f._LocalFile__archivedId
        repo = f._LocalFile__repository
        path = os.path.join(archive_path, repo._MaterialLocalRepository__files[archive_id])
        if os.path.exists(path):
            return f.fileName, path
        for mode, enc in (('strict', 'iso-8859-1'), ('replace', sys.getfilesystemencoding()), ('replace', 'ascii')):
            enc_path = path.decode('utf-8', mode).encode(enc, 'replace')
            if os.path.exists(enc_path):
                return f.fileName, enc_path
        return f.fileName, None

    def _iter_csbms(self):
        idx = self.zodb_root['catalog']['cs_bookingmanager_conference']._tree
        for csbm in self.flushing_iterator(idx.itervalues()):
            if not csbm._bookingsByType.get('WebcastRequest') and not csbm._bookingsByType.get('RecordingRequest'):
                continue
            yield csbm
