# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

"""
Synchronizes rooms and equipment with the CERN Foundation Database.
"""

from __future__ import unicode_literals

import sys
from logging import StreamHandler

import click
from celery.schedules import crontab
from wtforms import StringField

from indico.cli.core import cli_command
from indico.core import signals
from indico.core.celery import celery
from indico.core.plugins import IndicoPlugin
from indico.web.forms.base import IndicoForm

from indico_foundationsync.sync import FoundationSync


class SettingsForm(IndicoForm):
    connection_string = StringField('Foundation DB')


class FoundationSyncPlugin(IndicoPlugin):
    """Foundation Sync

    Synchronizes rooms and equipment with the CERN Foundation Database.
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {'connection_string': ''}

    def init(self):
        super(FoundationSyncPlugin, self).init()
        self.connect(signals.plugin.cli, self._extend_indico_cli)

    def get_blueprints(self):
        from indico_foundationsync.blueprint import blueprint
        return blueprint

    def _extend_indico_cli(self, sender, **kwargs):
        @cli_command()
        @click.option('--room', 'room_name', metavar='ROOM', help="Synchronize only a given room (e.g. '513 R-055')")
        def foundationsync(room_name):
            """Synchronize rooms and equipment with the CERN Foundation Database"""
            db_name = self.settings.get('connection_string')
            if not db_name:
                print 'Foundation DB connection string is not set'
                sys.exit(1)

            # Log to stdout
            self.logger.addHandler(StreamHandler())
            FoundationSync(db_name, self.logger).run_all(room_name)
        return foundationsync


@celery.periodic_task(run_every=crontab(minute='0', hour='8'))
def scheduled_update(room_name=None):
    db_name = FoundationSyncPlugin.settings.get('connection_string')
    if not db_name:
        raise RuntimeError('Foundation DB connection string is not set')
    FoundationSync(db_name, FoundationSyncPlugin.logger).run_all(room_name)
