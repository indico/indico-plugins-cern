# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import defaultdict
from datetime import timedelta

from flask import g
from sqlalchemy.orm import subqueryload
from wtforms.fields import BooleanField, FloatField, IntegerField, SelectField, URLField
from wtforms.fields.simple import StringField
from wtforms.validators import URL, DataRequired, NumberRange

from indico.cli.core import cli_command
from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import TimedeltaConverter
from indico.modules.events import Event
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.users import ExtraUserPreferences
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField, MultipleItemsField, TimeDeltaField
from indico.web.forms.validators import HiddenUnless
from indico.web.forms.widgets import SwitchWidget

from indico_outlook import _
from indico_outlook.calendar import update_calendar
from indico_outlook.models.queue import OutlookAction, OutlookQueueEntry
from indico_outlook.util import get_registered_users, is_event_excluded, latest_actions_only


_status_choices = [('free', _('Free')),
                   ('busy', _('Busy')),
                   ('tentative', _('Tentative')),
                   ('oof', _('Out of office'))]


class SettingsForm(IndicoForm):
    debug = BooleanField(_('Debug mode'), widget=SwitchWidget(),
                         description=_('If enabled, requests are not sent to the API but logged instead'))
    service_url = URLField(_('Service URL'), [URL(require_tld=False)],
                           description=_('The URL of the CERN calendar service'))
    token = IndicoPasswordField(_('Token'), [DataRequired()], toggle=True,
                                description=_('The token used to authenticate with the CERN calendar service'))
    status = SelectField(_('Status'), [DataRequired()], choices=_status_choices,
                         description=_('The default status of the event in the calendar'))
    reminder = BooleanField(_('Reminder'), description=_('Enable calendar reminder'))
    reminder_minutes = IntegerField(_('Reminder time'), [NumberRange(min=0)],
                                    description=_('Remind users X minutes before the event'))
    id_prefix = StringField(_('Prefix'),
                            description=_('Prefix for calendar item IDs. If you change this, existing calendar entries '
                                          'cannot be deleted/updated anymore!'))
    timeout = FloatField(_('Request timeout'), [NumberRange(min=0.25)], description=_('Request timeout in seconds'))
    max_event_duration = TimeDeltaField(_('Maximum Duration'), [DataRequired()], units=('days',),
                                        description=_('Events lasting longer will not be sent to Exchange'))


class OutlookUserPreferences(ExtraUserPreferences):
    fields = {
        'outlook_active': BooleanField(
            _('Sync with Outlook'),
            widget=SwitchWidget(),
            description=_('Add Indico events to my Outlook calendar'),
        ),
        'outlook_registered': BooleanField(
            _('Sync event registrations with Outlook'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            widget=SwitchWidget(),
            description=_("Add to my Outlook calendar events I'm registered for"),
        ),
        'outlook_favorite_events': BooleanField(
            _('Sync favorite events with Outlook'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            widget=SwitchWidget(),
            description=_('Add to my Outlook calendar events that I mark as favorite'),
        ),
        'outlook_favorite_categories': BooleanField(
            _('Sync favorite categories with Outlook'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            widget=SwitchWidget(),
            description=_('Add to my Outlook calendar all events in categories (and their subcategories) '
                          'I mark as favorite'),
        ),
        'outlook_status': SelectField(
            _('Outlook entry status'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            choices=_status_choices,
            description=_('The status for Outlook Calendar entries'),
        ),
        'outlook_reminder': BooleanField(
            _('Outlook reminders'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            widget=SwitchWidget(),
            description=_('Enable reminder for Outlook Calendar entries'),
        ),
        'outlook_reminder_minutes': IntegerField(
            _('Outlook reminder time'),
            [HiddenUnless('extra_outlook_active', preserve_data=True), NumberRange(min=0)],
            description=_('Remind X minutes before the event'),
        ),
        'outlook_overrides': MultipleItemsField(
            _('Outlook overrides'),
            [HiddenUnless('extra_outlook_active', preserve_data=True)],
            fields=[
                {'id': 'type', 'caption': _('Type'), 'required': True, 'type': 'select'},
                {'id': 'id', 'caption': _('Category ID'), 'required': True, 'type': 'number', 'step': 1, 'coerce': int},
                {'id': 'status', 'caption': _('Status'), 'required': True, 'type': 'select'},
                {'id': 'reminder', 'caption': _('Reminder'), 'required': True, 'type': 'checkbox'},
                {
                    'id': 'reminder_minutes',
                    'caption': _('Reminder time'),
                    'required': True,
                    'type': 'number',
                    'step': 1,
                    'coerce': int,
                },
            ],
            choices={
                'type': {'category': _('Category'), 'category_tree': _('Category & Subcategories')},
                'status': dict(_status_choices),
            },
            description=_('You can override the calendar entry configuration for specific categories.'),
        ),
    }

    def load(self):
        default_status = OutlookPlugin.settings.get('status')
        default_reminder = OutlookPlugin.settings.get('reminder')
        default_reminder_minutes = OutlookPlugin.settings.get('reminder_minutes')
        return {
            'outlook_active': OutlookPlugin.user_settings.get(self.user, 'enabled'),
            'outlook_registered': OutlookPlugin.user_settings.get(self.user, 'registered'),
            'outlook_favorite_events': OutlookPlugin.user_settings.get(self.user, 'favorite_events'),
            'outlook_favorite_categories': OutlookPlugin.user_settings.get(self.user, 'favorite_categories'),
            'outlook_status': OutlookPlugin.user_settings.get(self.user, 'status', default_status),
            'outlook_reminder': OutlookPlugin.user_settings.get(self.user, 'reminder', default_reminder),
            'outlook_reminder_minutes': OutlookPlugin.user_settings.get(self.user,
                                                                        'reminder_minutes', default_reminder_minutes),
            'outlook_overrides': OutlookPlugin.user_settings.get(self.user, 'overrides', []),
        }

    def save(self, data):
        OutlookPlugin.user_settings.set_multi(self.user, {
            'enabled': data['outlook_active'],
            'registered': data['outlook_registered'],
            'favorite_events': data['outlook_favorite_events'],
            'favorite_categories': data['outlook_favorite_categories'],
            'status': data['outlook_status'],
            'reminder': data['outlook_reminder'],
            'reminder_minutes': data['outlook_reminder_minutes'],
            'overrides': data['outlook_overrides'],
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
        'token': None,
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
        'enabled': True,  # XXX: if the default value ever changes, adapt `get_registered_users`!
        'registered': True,
        'favorite_events': True,
        'favorite_categories': True,
        'status': None,
        'reminder': True,
        'reminder_minutes': 15,
        'overrides': [],
    }

    def init(self):
        super().init()
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.users.preferences, self.extend_user_preferences)
        self.connect(signals.event.registration.registration_form_deleted, self.event_registration_form_deleted)
        self.connect(signals.event.registration.registration_state_updated, self.event_registration_state_changed)
        self.connect(signals.event.registration.registration_deleted, self.event_registration_deleted)
        self.connect(signals.event.updated, self.event_updated)
        self.connect(signals.event.times_changed, self.event_times_changed, sender=Event)
        self.connect(signals.event.created, self.event_created)
        self.connect(signals.event.restored, self.event_created)
        self.connect(signals.event.deleted, self.event_deleted)
        self.connect(signals.core.after_process, self._apply_changes)
        self.connect(signals.users.merged, self._merge_users)
        self.connect(signals.users.favorite_event_added, self.favorite_event_added)
        self.connect(signals.users.favorite_event_removed, self.favorite_event_removed)
        self.connect(signals.users.favorite_category_added, self.favorite_category_added)
        self.connect(signals.users.favorite_category_removed, self.favorite_category_removed)

    def _extend_indico_cli(self, sender, **kwargs):
        @cli_command()
        def outlook():
            """Synchronizes Outlook calendars."""
            update_calendar()
        return outlook

    def extend_user_preferences(self, user, **kwargs):
        return OutlookUserPreferences

    def _user_tracks_registered_events(self, user):
        return OutlookPlugin.user_settings.get(user, 'registered',
                                               OutlookPlugin.default_user_settings['registered'])

    def _user_tracks_favorite_events(self, user):
        return OutlookPlugin.user_settings.get(user, 'favorite_events',
                                               OutlookPlugin.default_user_settings['favorite_events'])

    def _user_tracks_favorite_categories(self, user):
        return OutlookPlugin.user_settings.get(user, 'favorite_categories',
                                               OutlookPlugin.default_user_settings['favorite_categories'])

    def favorite_event_added(self, user, event, **kwargs):
        if not self._user_tracks_favorite_events(user):
            return
        self._record_change(event, user, OutlookAction.add)
        self.logger.info('Favorite event added: updating %s in %r', user, event)

    def favorite_event_removed(self, user, event, **kwargs):
        if not self._user_tracks_favorite_events(user):
            return
        self._record_change(event, user, OutlookAction.remove)
        self.logger.info('Favorite event removed: updating %s in %r', user, event)

    def favorite_category_added(self, user, category, **kwargs):
        if not self._user_tracks_favorite_categories(user):
            return

        query = (Event.query
                 .filter(Event.is_visible_in(category.id),
                         Event.start_dt > now_utc(),
                         ~Event.is_deleted)
                 .options(subqueryload('acl_entries'))
                 .order_by(Event.start_dt, Event.id))
        events = [e for e in query if e.can_access(user)]
        for event in events:
            self._record_change(event, user, OutlookAction.add)
            self.logger.info('Favorite category added: user %s added event %r', user, event)

        self.logger.info('Favorite category added: updating %s in %r', user, category)

    def favorite_category_removed(self, user, category, **kwargs):
        if not self._user_tracks_favorite_categories(user):
            return

        query = (Event.query
                 .filter(Event.is_visible_in(category.id),
                         Event.start_dt > now_utc(),
                         ~Event.is_deleted)
                 .options(subqueryload('acl_entries'))
                 .order_by(Event.start_dt, Event.id))
        events = [e for e in query if e.can_access(user)]
        for event in events:
            self._record_change(event, user, OutlookAction.remove)
            self.logger.info('Favorite category added: user %s added event %r', user, event)

        self.logger.info('Favorite category removed: updating %s in %r', user, category)

    def event_registration_state_changed(self, registration, **kwargs):
        if not registration.user or not self._user_tracks_registered_events(registration.user):
            return
        if registration.state == RegistrationState.complete:
            event = registration.registration_form.event
            self._record_change(event, registration.user, OutlookAction.add)
            self.logger.info('Registration added: adding %s in %r', registration.user, event)
        elif registration.state == RegistrationState.withdrawn:
            event = registration.registration_form.event
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration withdrawn: removing %s in %r', registration.user, event)

    def event_registration_deleted(self, registration, **kwargs):
        if registration.user and self._user_tracks_registered_events(registration.user):
            event = registration.registration_form.event
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration removed: removing %s in %r', registration.user, event)

    def event_registration_form_deleted(self, registration_form, **kwargs):
        """In this case we will emit "remove" actions for all participants in `registration_form`"""
        event = registration_form.event
        for registration in registration_form.active_registrations:
            if not (registration.user and self._user_tracks_registered_events(registration.user)):
                continue
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration removed (form deleted): removing %s in %s', registration.user, event)

    def event_updated(self, event, changes, **kwargs):
        monitored_keys = {'title', 'description', 'location_data', 'person_links', 'start_dt', 'end_dt', 'duration'}
        if not changes.keys() & monitored_keys:
            return

        users_to_update = set()
        # Registered users need to be informed about changes
        for user in get_registered_users(event):
            if self._user_tracks_registered_events(user):
                users_to_update.add(user)

        # Users that have marked the event as favorite too
        for user in event.favorite_of:
            if self._user_tracks_favorite_events(user):
                users_to_update.add(user)

        for category in reversed(event.category.chain_query.all()):
            for user in category.favorite_of:
                if self._user_tracks_favorite_categories(user) and event.can_access(user):
                    users_to_update.add(user)
            # Stop once we reach the visibility horizon of the event
            if category is event.category.real_visibility_horizon:
                break

        for user in users_to_update:
            self.logger.info('Event data change: updating %s in %r', user, event)
            self._record_change(event, user, OutlookAction.update)

    def event_times_changed(self, sender, obj, **kwargs):
        event = obj
        changes = kwargs['changes']
        del kwargs['changes']

        self.logger.info('Event time change: updating %r: %r', event, changes)
        self.event_updated(event, changes, **kwargs)

    def event_created(self, event, **kwargs):
        self.logger.info('Event created: %r', event)
        # Piggyback on the event_updated handler to avoid duplicating the logic
        self.event_updated(event, {'title': event.title}, **kwargs)

    def event_deleted(self, event, **kwargs):
        users_to_update = set()
        for user in get_registered_users(event):
            if self._user_tracks_registered_events(user):
                users_to_update.add(user)
        for user in event.favorite_of:
            if self._user_tracks_favorite_events(user):
                users_to_update.add(user)
        for category in reversed(event.category.chain_query.all()):
            for user in category.favorite_of:
                if self._user_tracks_favorite_categories(user) and event.can_access(user):
                    users_to_update.add(user)
            # Stop once we reach the visibility horizon of the event
            if category is event.category.real_visibility_horizon:
                break

        for user in users_to_update:
            self.logger.info('Event deletion: removing %s in %r', user, event)
            self._record_change(event, user, OutlookAction.remove, force_remove=True)

    def _record_change(self, event, user, action, force_remove=False):
        if is_event_excluded(event):
            return
        if 'outlook_changes' not in g:
            g.outlook_changes = []

        if action == OutlookAction.remove and not force_remove:
            # Only remove an event if the user *really* shouldn't have it in their calendar

            if user in get_registered_users(event) and self._user_tracks_registered_events(user):
                return
            if user in event.favorite_of and self._user_tracks_favorite_events(user):
                return
            if self._user_tracks_favorite_categories(user):
                for category in reversed(event.category.chain_query.all()):
                    if (
                        user in category.favorite_of
                        and event.can_access(user)
                    ):
                        return
                    # Stop once we reach the visibility horizon of the event
                    if category is event.category.real_visibility_horizon:
                        break

        g.outlook_changes.append((event, user, action))

    def _apply_changes(self, sender, **kwargs):
        # we are using after_request to avoid unnecessary db deletes+inserts for the same entry since
        # especially event_data_changes is often triggered more than once e.g. for most date changes
        if 'outlook_changes' not in g:
            return
        user_events = defaultdict(list)
        for event, user, action in g.outlook_changes:
            user_events[(user, event)].append(action)
        for (user, event), data in user_events.items():
            for action in latest_actions_only(data):
                OutlookQueueEntry.record(event, user, action)

    def _merge_users(self, target, source, **kwargs):
        OutlookQueueEntry.query.filter_by(user_id=source.id).update({OutlookQueueEntry.user_id: target.id})
