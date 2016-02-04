from __future__ import unicode_literals

from collections import defaultdict
from operator import itemgetter

from flask import g
from flask_pluginengine import with_plugin_context
from wtforms.fields.core import SelectField, BooleanField, FloatField
from wtforms.fields.html5 import URLField, IntegerField
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, NumberRange, URL

from indico.core import signals
from indico.core.db import DBMgr, db
from indico.core.db.sqlalchemy.util.session import update_session_options
from indico.core.plugins import IndicoPlugin
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.users import ExtraUserPreferences
from indico.util.event import unify_event_args
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico.web.forms.widgets import SwitchWidget

from indico_outlook import _
from indico_outlook.calendar import update_calendar
from indico_outlook.models.queue import OutlookQueueEntry, OutlookAction
from indico_outlook.util import get_participating_users, latest_actions_only


_status_choices = [('free', _('Free')),
                   ('busy', _('Busy')),
                   ('tentative', _('Tentative')),
                   ('oof', _('Out of office'))]


class SettingsForm(IndicoForm):
    debug = BooleanField(_('Debug mode'),
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


class OutlookUserPreferences(ExtraUserPreferences):
    fields = {
        'outlook_active': BooleanField(_('Sync with Outlook'), widget=SwitchWidget(),
                                       description=_('Add Indico events in which I participate to my Outlook calendar'))
    }

    def load(self):
        return {'outlook_active': OutlookPlugin.user_settings.get(self.user, 'enabled')}

    def save(self, data):
        OutlookPlugin.user_settings.set(self.user, 'enabled', data['outlook_active'])


class OutlookPlugin(IndicoPlugin):
    """Outlook Integration

    Enables outlook calendar notifications when a user registers in a conference or participates in a meeting/lecture.
    """
    configurable = True
    settings_form = SettingsForm
    strict_settings = True
    default_settings = {
        'debug': False,
        'service_url': None,
        'username': None,
        'password': None,
        'status': 'free',
        'reminder': True,
        'reminder_minutes': 15,
        'id_prefix': 'indico_',
        'timeout': 3
    }
    default_user_settings = {
        'enabled': True  # XXX: if the default value ever changes, adapt `get_participating_users`!
    }

    def init(self):
        super(OutlookPlugin, self).init()
        self.connect(signals.users.preferences, self.extend_user_preferences)
        self.connect(signals.event.registration.registration_state_updated, self.event_registration_state_changed)
        self.connect(signals.event.registration.registration_deleted, self.event_registration_deleted)
        self.connect(signals.event.data_changed, self.event_data_changed)
        self.connect(signals.event.deleted, self.event_deleted)
        self.connect(signals.after_process, self._apply_changes)
        self.connect(signals.before_retry, self._clear_changes)
        self.connect(signals.users.merged, self._merge_users)

    def add_cli_command(self, manager):
        @manager.command
        @with_plugin_context(self)
        def outlook():
            """Synchronizes Outlook calendars"""
            update_session_options(db)
            with DBMgr.getInstance().global_connection():
                update_calendar()

    def extend_user_preferences(self, user, **kwargs):
        return OutlookUserPreferences

    def event_registration_state_changed(self, registration, **kwargs):
        if registration.user and registration.state == RegistrationState.complete:
            event = registration.registration_form.event_new
            self._record_change(event, registration.user, OutlookAction.add)
            self.logger.info('Registration added: adding %s in %r', registration.user, event)

    def event_registration_deleted(self, registration, **kwargs):
        if registration.user:
            event = registration.registration_form.event_new
            self._record_change(event, registration.user, OutlookAction.remove)
            self.logger.info('Registration removed: removing %s in %r', registration.user, event)

    @unify_event_args
    def event_data_changed(self, event, attr, **kwargs):
        for user in get_participating_users(event):
            self.logger.info('Event data change (%s): updating %s in %r', attr, user, event)
            self._record_change(event, user, OutlookAction.update)

    @unify_event_args
    def event_deleted(self, event, **kwargs):
        for user in get_participating_users(event):
            self.logger.info('Event deletion: removing %s in %r', user, event)
            self._record_change(event, user, OutlookAction.remove)

    def _record_change(self, event, user, action):
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

    def _clear_changes(self, sender, **kwargs):
        if 'outlook_changes' not in g:
            return
        del g.outlook_changes

    def _merge_users(self, target, source, **kwargs):
        OutlookQueueEntry.find(user_id=source.id).update({OutlookQueueEntry.user_id: target.id})
