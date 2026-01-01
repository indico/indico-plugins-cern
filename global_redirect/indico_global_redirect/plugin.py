# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import functools
from urllib.parse import urlsplit, urlunsplit

from flask import current_app, flash, redirect, request
from markupsafe import Markup
from werkzeug.exceptions import Forbidden
from wtforms import BooleanField, IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, NumberRange

from indico.core import signals
from indico.core.db import db
from indico.core.errors import NoReportError
from indico.core.plugins import IndicoPlugin
from indico.modules.events import Event
from indico.modules.events.forms import EventCreationFormBase
from indico.modules.events.management.forms import CloneCategorySelectForm
from indico.web.flask.util import url_for
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget

from indico_global_redirect.blueprint import blueprint
from indico_global_redirect.cli import cli
from indico_global_redirect.models.id_map import GlobalIdMap


ID_ARG_MAP = {
    'category_id': 'categories.categories.id',
    'subcontrib_id': 'events.subcontributions.id',
    'contrib_id': 'events.contributions.id',
    'entry_id': 'events.timetable_entries.id',
    'session_id': 'events.sessions.id',
    'event_id': 'events.events.id',
    'folder_id': 'attachments.folders.id',
    'attachment_id': 'attachments.attachments.id',
    'abstract_id': 'event_abstracts.abstracts.id',
    'reg_form_id': 'event_registration.forms.id',
    'registration_id': 'event_registration.registrations.id',
    'survey_id': 'event_surveys.surveys.id',
    'track_id': 'events.tracks.id',
    'page_id': 'events.pages.id',
    'file_id': 'indico.files.id',
    'image_id': 'events.image_files.id',
}

CUSTOM_ASSETS_BLUEPRINTS = {'event_images'}
CUSTOM_ASSETS_ENDPOINTS = {'event_layout.css_display', 'categories.display_logo', 'categories.display_icon'}
ALLOWED_NON_GET_ENDPOINTS = {'categories.show_future_events', 'categories.show_past_events'}


class PluginSettingsForm(IndicoForm):
    global_hostname = StringField('Global hostname', [DataRequired()],
                                  description='The hostname of Indico Global to be used in redirects')
    testing = BooleanField('Testing mode', widget=SwitchWidget(),
                           description='Flash the target URL instead of redirecting')
    permanent_redirects = BooleanField('Permanent redirects', widget=SwitchWidget(),
                                       description='Use permanent (HTTP 301) redirects')
    global_category_id = IntegerField('Global category ID', [DataRequired(), NumberRange(min=1)],
                                      description='The ID of the "Indico Global" category id')
    read_only = BooleanField('Make global category read-only', widget=SwitchWidget(),
                             description='Prevents any non-GET requests for categories and events within the '
                                         'Global category')
    read_only_msg = TextAreaField('Read-only message',
                                  description='Displayed in all events/categories within the Global category when '
                                              'read-only mode is enabled')
    allow_cat_notifications = BooleanField('Allow sending category notifications', widget=SwitchWidget(),
                                           description='Enable this to allow notifying category managers via the CLI.')
    allow_event_notifications = BooleanField('Allow sending event notifications', widget=SwitchWidget(),
                                             description='Enable this to allow notifying event managers via the CLI.')
    allow_event_notifications_zoom = BooleanField('Allow sending event notifications for Zoom', widget=SwitchWidget(),
                                             description='Enable this to allow notifying event managers with Zoom '
                                                         'meetings via the CLI.')


@functools.lru_cache(maxsize=1)
def _get_primary_mappings(_mapping_cache_version):
    return {
        'events.events.id': {x.local_id: x.global_id for x in GlobalIdMap.query.filter_by(col='events.events.id')},
        'categories.categories.id': {
            x.local_id: x.global_id for x in GlobalIdMap.query.filter_by(col='categories.categories.id')
        },
    }


@functools.cache
def _map_global_ids(**id_view_args):
    new_ids = {}
    for key, local_id in id_view_args.items():
        col = ID_ARG_MAP[key]
        new_ids[key] = GlobalIdMap.get_global_id(col, int(local_id))
    return new_ids


def _is_request_likely_seen():
    return (
        request.method == 'GET'
        and not request.is_xhr
        and not request.is_json
        and request.blueprint not in CUSTOM_ASSETS_BLUEPRINTS
        and request.endpoint not in CUSTOM_ASSETS_ENDPOINTS
    )


class GlobalRedirectPlugin(IndicoPlugin):
    """Indico Global Redirect

    Provides functionality related to Indico Global on the main Indico instance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {
        'global_hostname': 'indico.global',
        'testing': False,
        'permanent_redirects': False,
        'global_category_id': None,
        'read_only': False,
        'read_only_msg': '',
        'allow_cat_notifications': False,
        'allow_event_notifications': False,
        'allow_event_notifications_zoom': False,
        'mapping_cache_version': 1,
    }

    def init(self):
        super().init()
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.rh.before_process, self._before_rh_process)
        self.connect(signals.core.form_validated, self._event_creation_form_validated)
        current_app.before_request(self._before_request)

    def _extend_indico_cli(self, sender, **kwargs):
        return cli

    def get_blueprints(self):
        return blueprint

    def _event_creation_form_validated(self, form, **kwargs):
        match form:
            case EventCreationFormBase():
                if not form.listing.data:
                    return
            case CloneCategorySelectForm():
                # cannot clone to unlisted atm, so nothing special to do here yet
                pass
            case _:
                return
        if not self.settings.get('read_only') or (global_id := self.settings.get('global_category_id')) is None:
            return
        if global_id not in form.category.data.chain_ids:
            return
        form.category.errors.append(self.settings.get('read_only_msg') or 'This category is read-only.')
        return False

    def _before_rh_process(self, rh_cls, rh, **kwargs):
        if not self.settings.get('read_only') or (global_id := self.settings.get('global_category_id')) is None:
            return

        categories = set()
        if (event := getattr(rh, 'event', None)) and event.category:
            categories.add(event.category)
        elif category := getattr(rh, 'category', None):
            categories.add(category)

        # moving events/categories
        if target_category := getattr(rh, 'target_category', None):
            categories.add(target_category)

        if not any(global_id in cat.chain_ids for cat in categories):
            return

        if (msg := self.settings.get('read_only_msg')) and _is_request_likely_seen():
            flash(msg, 'info')
        elif request.method not in ('GET', 'HEAD') and request.endpoint not in ALLOWED_NON_GET_ENDPOINTS:
            raise NoReportError.wrap_exc(Forbidden(msg or 'This event/category is read-only.'))

    def _before_request(self):
        if request.method != 'GET' or not request.endpoint:
            return

        if request.blueprint == 'assets' or request.endpoint.endswith('.static'):
            # those never need redirecting
            return

        primary_mappings = _get_primary_mappings(self.settings.get('mapping_cache_version'))
        id_view_args = {k: v for k, v in request.view_args.items() if k.endswith('_id')}
        event_id = category_id = None
        if (event_id := id_view_args.get('event_id')) is not None:
            try:
                if int(event_id) not in primary_mappings['events.events.id']:
                    return
                event_id = int(event_id)
            except ValueError:
                # non-numeric event id (e.g. shortcut url)
                query = db.session.query(Event.id).filter(db.func.lower(Event.url_shortcut) == event_id.lower())
                event_id = next((id for id, in query if id in primary_mappings['events.events.id']), None)
                if event_id is None:
                    return
                id_view_args['event_id'] = event_id
        elif (category_id := id_view_args.get('category_id')) is not None:
            try:
                if int(category_id) not in primary_mappings['categories.categories.id']:
                    return
                category_id = int(category_id)
            except ValueError:
                # no category id or non-numeric
                return
        else:
            # not an event/category page
            return

        if (
            set(id_view_args) <= set(ID_ARG_MAP) and
            (new_ids := _map_global_ids(**id_view_args)) and
            # avoid breakage when the ids do not match, e.g. a session id from a different event.
            # in that case we get None for the wrong id, and thus building the URL would fail
            None not in new_ids.values()
        ):
            if request.endpoint == 'papers.download_file':
                # this one uses file_id for PaperFile for which we do not have an ID mapping
                new_url_path = url_for('contributions.display_contribution', event_id=new_ids['event_id'],
                                       contrib_id=new_ids['contrib_id'])
            else:
                new_url_path = url_for(request.endpoint, **{**request.view_args, **new_ids})
        elif event_id is not None:
            if self.settings.get('testing'):
                print('\n\nSome ids not mapped, using just the event id\n\n')
                flash('Not all ids mapped, using event home page instead', 'warning')
            global_event_id = primary_mappings['events.events.id'][event_id]
            new_url_path = url_for('events.display', event_id=global_event_id)
        elif category_id is not None:
            if self.settings.get('testing'):
                print('\n\nSome ids not mapped, using just the category id\n\n')
                flash('Not all ids mapped, using category home page instead', 'warning')
            global_category_id = primary_mappings['categories.categories.id'][category_id]
            new_url_path = url_for('categories.display', category_id=global_category_id)
        else:
            # never supposed to happen
            return

        url = urlsplit(request.url)
        new_url = urlunsplit(url._replace(netloc=self.settings.get('global_hostname'), path=new_url_path))
        if self.settings.get('testing'):
            print(f'Indico Global URL: {new_url}')
            if _is_request_likely_seen():
                flash(Markup(f'Indico Global version of this page: <a href="{new_url}">{new_url}</a>'))
        else:
            return redirect(new_url, 301 if self.settings.get('permanent_redirects') else 302)
