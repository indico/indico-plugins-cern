from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode

from indico_requests_audiovisual.plugin import AVRequestsPlugin


class AVRequestsImporter(Importer):
    plugins = {'requests_audiovisual'}

    def migrate(self):
        raise NotImplementedError
