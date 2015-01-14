from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico_zodbimport import Importer, convert_to_unicode

from indico_search_cern.plugin import CERNSearchPlugin


class CERNSearchImporter(Importer):
    plugins = {'search', 'search_cern'}

    def migrate(self):
        self.migrate_settings()

    def migrate_settings(self):
        print cformat('%{white!}migrating settings')
        CERNSearchPlugin.settings.delete_all()
        opts = self.zodb_root['plugins']['search']._PluginType__plugins['cern_search']._PluginBase__options
        CERNSearchPlugin.settings.set('search_url', convert_to_unicode(opts['serverUrl']._PluginOption__value).strip())
        db.session.commit()
