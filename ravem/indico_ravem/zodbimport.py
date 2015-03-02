from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico_zodbimport import Importer, option_value

from indico_ravem.plugin import RavemPlugin


class RavemImporter(Importer):
    plugins = {'vc_vidyo', 'ravem'}

    def migrate(self):
        self.migrate_settings()

    def migrate_settings(self):
        print cformat('%{white!}migrating settings')
        RavemPlugin.settings.delete_all()

        opts = self.zodb_root['plugins']['Collaboration']._PluginBase__options
        settings_map = {
            'ravemAPIURL': 'api_endpoint',
            'ravemUsername': 'username',
            'ravemPassword': 'password'
        }

        for old, new in settings_map.iteritems():
            value = option_value(opts[old])
            if new == 'api_endpoint':
                value = value.rstrip('/') + '/'
            RavemPlugin.settings.set(new, value)

        vidyo_opts = self.zodb_root['plugins']['Collaboration']._PluginType__plugins['Vidyo']._PluginBase__options
        RavemPlugin.settings.set('prefix', int(option_value(vidyo_opts['prefixConnect'])))

        db.session.commit()
