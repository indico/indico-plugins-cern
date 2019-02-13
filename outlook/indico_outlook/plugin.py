# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from collections import defaultdict
from datetime import timedelta

from flask import g
from wtforms.fields.core import BooleanField, FloatField, SelectField
from wtforms.fields.html5 import IntegerField, URLField
from wtforms.fields.simple import StringField
from wtforms.validators import URL, DataRequired, NumberRange

from indico.cli.core import cli_command
from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import TimedeltaConverter
from indico.modules.events import Event
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.users import ExtraUserPreferences
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField, TimeDeltaField
from indico.web.forms.validators import HiddenUnless
from indico.web.forms.widgets import SwitchWidget

from indico_outlook import _
from indico_outlook.calendar import update_calendar
from indico_outlook.models.queue import OutlookAction, OutlookQueueEntry
from indico_outlook.util import get_participating_users, is_event_excluded, latest_actions_only


_status_choices = [('free', _('Free')),
                   ('busy', _('Busy')),
                   ('tentative', _('Tentative')),
                   ('oof', _('Out of office'))]


class SettingsForm(IndicoForm):
    debug = BooleanField(_('Debug mode'), widget=SwitchWidget(),
                         description=_("If enabled, requests are not sent to the API but logged instead"))
    service_url = URLField(_('Service URL'), [URL(require_tld=False)],
                           description=_("The URL of the CERN calendar service"))
    username = StringField(_('Username'), [DataRequired()],
                           description=_("The username used to authenticate with the CERN calendar service"))
    password = IndicoPasswordField(_('Password'), [DataRequired()], toggle=True,
                                   description=_("The password used to authenticate with the CERN calendar service"))
    status = SelectField(_('Status'), [DataRequired()], choices=_status_choices,
                         description=_("The default status of the event in the calendar"))
    reminder = BooleanField(_('Reminder'), description=_("Enable calendar reminder"))
    reminder_minutes = IntegerField(_('Reminder time'), [NumberRange(min=0)],
                                    description=_("Remind users X minutes before the event"))
    id_prefix = StringField(_('Prefix'),
                            description=_("Prefix for calendar item IDs. If you change this, existing calendar entries "
                                          "cannot be deleted/updated anymore!"))
    timeout = FloatField(_('Request timeout'), [NumberRange(min=0.25)], description=_("Request timeout in seconds"))
    max_event_duration = TimeDeltaField(_('Maximum Duration'), [DataRequired()], units=('days',),
                                        description=_('Events lasting longer will not be sent to Exchange'))


class OutlookUserPreferences(ExtraUserPreferences):
    fields = {
        'outlook_active': BooleanField(_('Sync with Outlook'), widget=SwitchWidget(),
                                       description=_('Add Indico events in which I participate to my Outlook '
                                                     'calendar')),
        'outlook_status': SelectField(_('Outlook entry status'), [HiddenUnless('extra_outlook_active',
                                                                               preserve_data=True)],
                                      choices=_status_choices,
                                      description=_('The status for Outlook Calendar entries'))
    }

    def load(self):
        default_status = OutlookPlugin.settings.get('status')
        return {
            'outlook_active': OutlookPlugin.user_settings.get(self.user, 'enabled'),
            'outlook_status': OutlookPlugin.user_settings.get(self.user, 'status', default_status)
        }

    def save(self, data):
        OutlookPlugin.user_settings.set_multi(self.user, {
            'enabled': data['outlook_active'],
            'status': data['outlook_status']
        })


class OutlookPlugin(IndicoPlugin):
    """Outlook Integration

    Enables outlook calendar notifications when a user registers in a conference or participates in a meeting/lecture.
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'debug': False,
        'service_url': None,
        'username': None,
        'password': None,
        'status': 'free',
        'reminder': True,
        'reminder_minutes': 15,
        'id_prefix': 'indico_',
        'timeout': 3,
        'max_event_duration': timedelta(days=30)
    }
    settings_converters = {
        'max_event_duration': TimedeltaConverter
    }
    default_user_settings = {
        'enabled': True,  # XXX: if the default value ever changes, adapt `get_participating_users`!
        'status': None
    }

    def init(self):
        super(OutlookPlugin, self).init()
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.users.preferences, self.extend_user_preferences)
        self.connect(signals.event.registration.registration_form_deleted, self.event_registration_form_deleted)
        self.connect(signals.event.registration.registration_state_updated, self.event_registration_state_changed)
        self.connect(signals.event.registration.registration_deleted, self.event_registration_deleted)
        self.connect(signals.event.updated, self.event_updated)
        self.connect(signals.event.times_changed, self.event_times_changed, sender=Event)
        self.connect(signals.event.deleted, self.event_deleted)
        self.connect(signals.after_process, self._apply_changes)
        self.connect(signals.users.merged, self._merge_users)

    def _extend_indico_cli(self, sender, **kwargs):
        @cli_command()
        def outlook():
            """Synchronizes Outlook calendars."""
            update_calendar()
        return outlook

    def extend_user_preferences(self, user, **kwargs):
        return OutlookUserPreferences

    def event_registration_state_changed(self, registration, **kwargs):
        if registration.user and registration.state == RegistrationState.complete:
            event = registration.registration_form.event
            self._record_change(event, registration.user, OutlookAction.add)
            self.logger.info('Registration added: adding %s in %r', registration.user, event)

    def event_registration_deleted(self, registration, **kwargs):
        if registration.user:
            event = registration.registration_form.event
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration removed: removing %s in %r', registration.user, event)

    def event_registration_form_deleted(self, registration_form, **kwargs):
        """In this case we will emit "remove" actions for all participants in `registration_form`"""
        event = registration_form.event
        for registration in registration_form.active_registrations:
            if not registration.user:
                continue
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration removed (form deleted): removing %s in %s', registration.user, event)

    def event_updated(self, event, changes, **kwargs):
        if not changes.viewkeys() & {'title', 'description', 'location_data'}:
            return
        for user in get_participating_users(event):
            self.logger.info('Event data change: updating %s in %r', user, event)
            self._record_change(event, user, OutlookAction.update)

    def event_times_changed(self, sender, obj, **kwargs):
        event = obj
        for user in get_participating_users(event):
            self.logger.info('Event time change: updating %s in %r', user, event)
            self._record_change(event, user, OutlookAction.update)

    def event_deleted(self, event, **kwargs):
        for user in get_participating_users(event):
            self.logger.info('Event deletion: removing %s in %r', user, event)
            self._record_change(event, user, OutlookAction.remove)

    def _record_change(self, event, user, action):
        if is_event_excluded(event):
            return
        if 'outlook_changes' not in g:
            g.outlook_changes = []
        g.outlook_changes.append((event, user, action))

    def _apply_changes(self, sender, **kwargs):
        # we are using after_request to avoid unnecessary db deletes+inserts for the same entry since
        # especially event_data_changes is often triggered more than once e.g. for most date changes
        if 'outlook_changes' not in g:
            return
        user_events = defaultdict(list)
        for event, user, action in g.outlook_changes:
            user_events[(user, event)].append(action)
        for (user, event), data in user_events.viewitems():
            for action in latest_actions_only(data):
                OutlookQueueEntry.record(event, user, action)

    def _merge_users(self, target, source, **kwargs):
        OutlookQueueEntry.find(user_id=source.id).update({OutlookQueueEntry.user_id: target.id})
