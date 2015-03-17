from __future__ import unicode_literals

import sys
from operator import itemgetter

from dateutil import rrule
from flask import g
from flask_pluginengine import with_plugin_context, render_plugin_template
from wtforms.fields.core import SelectField, BooleanField, FloatField
from wtforms.fields.html5 import URLField, IntegerField
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, NumberRange, URL

from indico.core import signals
from indico.core.db import DBMgr, db
from indico.core.db.sqlalchemy.util.session import update_session_options
from indico.core.plugins import IndicoPlugin
from indico.modules.scheduler import Client
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField

from indico_outlook import _
from indico_outlook.blueprint import blueprint
from indico_outlook.calendar import update_calendar, OutlookTask
from indico_outlook.models.blacklist import OutlookBlacklistUser
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


class OutlookPlugin(IndicoPlugin):
    """Outlook Integration

    Enables outlook calendar notifications when a user registers in a conference or participates in a meeting/lecture.
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'debug': False,
        'status': 'free',
        'reminder': True,
        'reminder_minutes': 15,
        'prefix': 'indico_',
        'timeout': 3
    }

    def init(self):
        super(OutlookPlugin, self).init()
        self.connect(signals.user_preferences, self.extend_user_preferences)
        self.connect(signals.event.registrant_changed, self.event_participation_changed)
        self.connect(signals.event.participant_changed, self.event_participation_changed)
        self.connect(signals.event.data_changed, self.event_data_changed)
        self.connect(signals.event.deleted, self.event_deleted)
        self.connect(signals.after_process, self._apply_changes)
        self.connect(signals.before_retry, self._clear_changes)

    def get_blueprints(self):
        return blueprint

    def add_cli_command(self, manager):
        @manager.option('--create-task', dest='create_task', metavar='N',
                        help='Create a task updating calendar entries every N minutes')
        @with_plugin_context(self)
        def outlook(create_task):
            """Synchronizes Outlook calendars"""
            update_session_options(db)
            if create_task:
                try:
                    interval = int(create_task)
                    if interval < 1:
                        raise ValueError
                except ValueError:
                    print 'Invalid interval, must be a number >=1'
                    sys.exit(1)
                with DBMgr.getInstance().global_connection(commit=True):
                    Client().enqueue(OutlookTask(rrule.MINUTELY, interval=interval))
                print 'Task created'
            else:
                with DBMgr.getInstance().global_connection():
                    update_calendar()

    def extend_user_preferences(self, user, **kwargs):
        active = not OutlookBlacklistUser.find_first(user_id=int(user.id))
        content = render_plugin_template('user_prefs.html', user=user, active=active)
        return _('Sync with my Outlook calendar'), content

    def event_participation_changed(self, event, user, action, **kwargs):
        if user:
            if action == 'added':
                self.logger.info('Participation change: adding {} in {!r}'.format(user, event))
                self._record_change(event, user, OutlookAction.add)
            elif action == 'removed':
                self.logger.info('Participation change: removing {} in {!r}'.format(user, event))
                self._record_change(event, user, OutlookAction.remove)

    def event_data_changed(self, event, attr, **kwargs):
        for user in get_participating_users(event):
            self.logger.info('Event data change ({}): updating {} in {!r}'.format(attr, user, event))
            self._record_change(event, user, OutlookAction.update)

    def event_deleted(self, event, **kwargs):
        for user in get_participating_users(event):
            self.logger.info('Event deletion: removing {} in {!r}'.format(user, event))
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
        for event, user, action in latest_actions_only(g.outlook_changes, itemgetter(2)):
            OutlookQueueEntry.record(event, user, action)

    def _clear_changes(self, sender, **kwargs):
        if 'outlook_changes' not in g:
            return
        del g.outlook_changes
