from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode

from indico_outlook.models.outlook_queue import OutlookQueueEntry, OutlookAction
from indico_outlook.plugin import OutlookPlugin


class OutlookImporter(Importer):
    plugins = {'outlook'}

    def pre_check(self):
        return self.check_plugin_schema('outlook')

    def has_data(self):
        return OutlookQueueEntry.find().count()

    def migrate(self):
        # noinspection PyAttributeOutsideInit
        self.outlook_root = self.zodb_root['plugins']['calendaring']._storage
        with OutlookPlugin.instance.plugin_context():
            self.migrate_settings()
            self.migrate_queue()

    def migrate_settings(self):
        print cformat('%{white!}migrating settings')
        OutlookPlugin.settings.delete_all()
        opts = self.zodb_root['plugins']['calendaring']._PluginType__plugins['outlook']._PluginBase__options
        settings_map = {
            'url': 'service_url',
            'login': 'username',
            'password': 'password',
            'status': 'status',
            'reminder': 'reminder',
            'reminder_minutes': 'reminder_minutes',
            'prefix': 'operation_prefix',
            'timeout': 'timeout'
        }
        for old, new in settings_map.iteritems():
            value = opts[old].getValue()
            if isinstance(value, basestring):
                value = convert_to_unicode(value).strip()
            OutlookPlugin.settings.set(new, value)
        db.session.commit()

    def migrate_queue(self):
        print cformat('%{white!}migrating queue')

        action_map = {
            'added': OutlookAction.add,
            'updated': OutlookAction.update,
            'removed': OutlookAction.remove,
        }

        for entries in committing_iterator(self.outlook_root.get('avatar_conference', {}).itervalues()):
            for entry in entries:
                if entry.get('request_sent'):
                    continue
                OutlookQueueEntry.record(entry['conference'], entry['avatar'], action_map[entry['eventType']])
