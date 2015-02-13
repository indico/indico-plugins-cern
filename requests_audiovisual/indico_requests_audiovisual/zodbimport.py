from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico.util.string import is_valid_mail
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode, convert_principal_list, option_value

from indico_requests_audiovisual.plugin import AVRequestsPlugin


class AVRequestsImporter(Importer):
    plugins = {'requests_audiovisual'}

    def migrate(self):
        self.migrate_settings()

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
        # TODO: anything agreement-related
        db.session.commit()
