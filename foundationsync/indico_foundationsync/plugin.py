# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from celery.schedules import crontab
from flask import g, session
from webargs import flaskparser
from wtforms import StringField
from wtforms.fields import BooleanField

from indico.core import signals
from indico.core.celery import celery
from indico.core.plugins import IndicoPlugin
from indico.modules.rb.schemas import RoomUpdateArgsSchema
from indico.modules.rb.util import rb_is_admin
from indico.modules.users.models.users import User
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget

from indico_foundationsync.cli import cli
from indico_foundationsync.sync import FoundationSync


SYNCED_FIELDS = {'building', 'floor', 'number', 'verbose_name', 'site', 'key_location', 'capacity', 'surface_area',
                 'telephone', 'division', 'latitude', 'longitude', 'owner'}
BLOCKED_FIELDS = {'protection_mode'}


class SettingsForm(IndicoForm):
    connection_string = StringField('Foundation DB')
    disable_sync = BooleanField(_('Disable sync'), widget=SwitchWidget(),
                                description=_('Temporarily disable synchronization with Foundation'))


class FoundationSyncPlugin(IndicoPlugin):
    """Foundation Sync

    Synchronizes rooms with the CERN Foundation Database.
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {'connection_string': '', 'disable_sync': False}

    def init(self):
        super().init()
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.plugin.schema_post_load, self._check_forbidden_fields, sender=RoomUpdateArgsSchema)

    def get_blueprints(self):
        from indico_foundationsync.blueprint import blueprint
        return blueprint

    def _check_forbidden_fields(self, sender, data, **kwargs):
        """Check that no one is trying to edit fields that come from Locations."""
        sync_collisions = set(data) & SYNCED_FIELDS
        blocked_collisions = set(data) & BLOCKED_FIELDS
        messages = {}

        messages.update({
            k: [_('This field is managed via the Locations application. You cannot change it from here.')]
            for k in sync_collisions
        })

        if blocked_collisions and not rb_is_admin(session.user):
            messages.update({
                k: [_('This field can only be changed by an administrator.')] for k in blocked_collisions
            })

        if 'acl_entries' in data:
            old_managers = g.rh.room.get_manager_list(include_groups=False)
            new_managers = {
                k for k, v in data['acl_entries'].items() if '_full_access' in v and isinstance(k, User)
            }
            if old_managers != new_managers:
                messages['acl_entries'] = [_('You cannot add/remove any individual managers. Please use an e-group.')]

        if messages:
            # our UI will be expecting code 422 for form validation errors
            flaskparser.abort(422, messages=messages)

    def _extend_indico_cli(self, sender, **kwargs):
        return cli


@celery.periodic_task(run_every=crontab(minute='0'))
def scheduled_update(room_name=None):
    if FoundationSyncPlugin.settings.get('disable_sync'):
        FoundationSyncPlugin.logger.warning('Sync is currently disabled')
        return
    dsn = FoundationSyncPlugin.settings.get('connection_string')
    if not dsn:
        raise RuntimeError('Foundation DB connection string is not set')
    FoundationSync(dsn, FoundationSyncPlugin.logger).run_all(room_name)
