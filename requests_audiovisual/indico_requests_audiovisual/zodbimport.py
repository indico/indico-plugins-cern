from __future__ import unicode_literals

from contextlib import contextmanager

from indico.core.config import Config
from indico.core.db import db
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.util.console import cformat
from indico.util.string import is_valid_mail
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode, convert_principal_list, option_value

from indico_requests_audiovisual.definition import AVRequest
from indico_requests_audiovisual.plugin import AVRequestsPlugin
from indico_requests_audiovisual.util import get_data_identifiers


class AVRequestsImporter(Importer):
    plugins = {'requests_audiovisual'}

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
        # TODO: migrate agreements

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
        # TODO: migrate agreement-related settings
        db.session.commit()

    def migrate_requests(self):
        print cformat('%{white!}migrating requests')
        status_map = {None: RequestState.pending,
                      True: RequestState.accepted,
                      False: RequestState.rejected}
        for csbm in committing_iterator(self._iter_csbms()):
            event = csbm._conf
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

    def _iter_csbms(self):
        idx = self.zodb_root['catalog']['cs_bookingmanager_conference']._tree
        for csbm in self.flushing_iterator(idx.itervalues()):
            if not csbm._bookingsByType.get('WebcastRequest') and not csbm._bookingsByType.get('RecordingRequest'):
                continue
            yield csbm
