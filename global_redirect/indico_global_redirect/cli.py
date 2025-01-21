# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import sys
import weakref
from collections import defaultdict
from datetime import datetime
from operator import attrgetter, itemgetter

import click
import yaml
from sqlalchemy.orm import subqueryload, undefer

from indico.cli.core import cli_group
from indico.core import signals
from indico.core.config import config
from indico.core.db import db
from indico.core.db.sqlalchemy.principals import PrincipalType
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.core.settings import SettingsProxyBase
from indico.modules.categories import Category, CategoryLogRealm
from indico.modules.categories.operations import delete_category
from indico.modules.events import Event, EventLogRealm
from indico.modules.logs import LogKind
from indico.util.console import verbose_iterator

from indico_global_redirect.models.id_map import GlobalIdMap


@cli_group(name='global')
def cli():
    """Manage the Global Redirect plugin."""


@cli.command()
@click.argument('mapping_file', type=click.File())
def load_mapping(mapping_file):
    """Import the ID mapping from YAML."""
    if GlobalIdMap.query.has_rows():
        click.secho('Mapping table is not empty', fg='yellow')
        if not click.confirm('Continue anyway?'):
            sys.exit(1)

    click.echo('Loading mapping data (this may take a while)...')
    mapping = yaml.safe_load(mapping_file)
    for col, data in mapping.items():
        click.echo(f'Processing {col}...')
        for local_id, global_id in verbose_iterator(data.items(), len(data), get_id=itemgetter(0)):
            GlobalIdMap.create(col, local_id, global_id)

    click.echo('Import finished, committing data...')
    db.session.commit()


@cli.command()
@click.argument('event_id', type=int)
@click.argument('category_id', type=int)
def demigrate_event(event_id, category_id):
    """Revert migration of an event.

    This moves the event to a new category outside Global Indico and undeletes it.
    """
    from indico_global_redirect.plugin import GlobalRedirectPlugin

    global_cat = Category.get(GlobalRedirectPlugin.settings.get('global_category_id'))
    event = Event.get(event_id)
    if event is None:
        click.secho('This event does not exist', fg='red')
        sys.exit(1)
    elif not event.is_deleted:
        click.secho('This event is not deleted', fg='yellow')
        sys.exit(1)
    elif global_cat.id not in event.category.chain_ids:
        click.secho('This event is not in Global Indico', fg='red')
        sys.exit(1)

    col = f'{Event.__table__.fullname}.{Event.id.name}'
    mapping = GlobalIdMap.query.filter_by(col=col, local_id=event.id).one_or_none()
    if mapping is None:
        click.secho('This event has no Global Indico mapping', fg='red')
        sys.exit(1)

    target_category = Category.get(category_id, is_deleted=False)
    if target_category is None:
        click.secho('This category does not exist', fg='red')
        sys.exit(1)
    elif global_cat.id in target_category.chain_ids:
        click.secho('This category is in Global Indico', fg='red')
        sys.exit(1)

    db.session.delete(mapping)
    event.move(target_category)
    event.restore('Reverted Global Indico migration')
    GlobalRedirectPlugin.settings.set('mapping_cache_version',
                                      GlobalRedirectPlugin.settings.get('mapping_cache_version') + 1)
    signals.core.after_process.send()
    db.session.commit()
    click.secho(f'Event restored: "{event.title}"', fg='green')


@cli.command()
def delete_migrated():
    """Mark migrated events + categories as deleted."""
    from indico_global_redirect.plugin import GlobalRedirectPlugin

    remove_handler_modules = {
        'indico.modules.rb',  # cancels physical room bookings
        'indico.modules.vc',  # deletes zoom meetings
        'indico_outlook.plugin',  # removes event from people's CERN calendars
        'indico_cern_access.plugin',  # revokes CERN visitor cards
    }
    for rcv in list(signals.event.deleted.receivers.values()):
        if isinstance(rcv, weakref.ref):
            rcv = rcv()
        if rcv.__module__ in remove_handler_modules:
            signals.event.deleted.disconnect(rcv)

    events = (
        Event.query.join(GlobalIdMap, db.and_(GlobalIdMap.local_id == Event.id,
                                              GlobalIdMap.col == 'events.events.id'))
        .filter(~Event.is_deleted)
        .all()
    )
    for event in verbose_iterator(events, len(events), get_id=attrgetter('id'), get_title=attrgetter('title')):
        event.delete('Migrated to Indico Global')

    global_cat_id = GlobalRedirectPlugin.settings.get('global_category_id')
    categories = (
        Category.query.join(GlobalIdMap, db.and_(GlobalIdMap.local_id == Category.id,
                                                 GlobalIdMap.col == 'categories.categories.id'))
        .filter(~Category.is_deleted, Category.id != global_cat_id)
        .all()
    )
    for cat in verbose_iterator(categories, len(categories), get_id=attrgetter('id'), get_title=attrgetter('title')):
        delete_category(cat)

    # make sure livesync picks up the event deletions
    signals.core.after_process.send()
    db.session.commit()


@cli.command()
def notify_category_managers():
    """Notify category managers about upcoming migration."""
    from indico_global_redirect.plugin import GlobalRedirectPlugin

    if not GlobalRedirectPlugin.settings.get('allow_cat_notifications'):
        click.echo('Category notifications are disabled (maybe already sent?)')
        return

    SettingsProxyBase.allow_cache_outside_request = True  # avoid re-querying site_title for every email
    global_cat = Category.get(GlobalRedirectPlugin.settings.get('global_category_id'))
    query = (global_cat.deep_children_query
            .filter(~Category.is_deleted, Category.acl_entries.any())
            .options(subqueryload(Category.acl_entries), undefer('chain_titles')))
    managers = defaultdict(set)
    managers_by_category = defaultdict(set)
    for cat in query:
        if not (cat_managers := {x.user for x in cat.acl_entries if x.full_access and x.type == PrincipalType.user}):
            continue
        for user in cat_managers:
            managers[user].add(cat)
            managers_by_category[cat].add(user)

    for user, cats in managers.items():
        group_acls = {
            x.multipass_group_name
            for cat in cats
            for x in cat.acl_entries if x.type == PrincipalType.multipass_group
        }
        tpl = get_plugin_template_module('emails/cat_notification.txt', name=user.first_name, categories=cats,
                                         group_acls=group_acls)
        send_email(make_email(to_list={user.email}, template=tpl,
                              sender_address=f'Indico Team <{config.NO_REPLY_EMAIL}>',
                              reply_address='indico-team@cern.ch'))

    for cat, users in managers_by_category.items():
        cat.log(CategoryLogRealm.category, LogKind.other, 'Indico Global', 'Sent migration notifications',
                data={'Recipient IDs': ', '.join(map(str, sorted(u.id for u in users))),
                      'Recipients': ', '.join(sorted(u.full_name for u in users))})

    GlobalRedirectPlugin.settings.set('allow_cat_notifications', False)
    db.session.commit()


@cli.command()
def notify_event_managers():
    """Notify event managers about upcoming migration."""
    from indico_global_redirect.plugin import GlobalRedirectPlugin

    if not GlobalRedirectPlugin.settings.get('allow_event_notifications'):
        click.echo('Event notifications are disabled (maybe already sent?)')
        return

    SettingsProxyBase.allow_cache_outside_request = True  # avoid re-querying site_title for every email
    global_cat = Category.get(GlobalRedirectPlugin.settings.get('global_category_id'))
    query = (Event.query
            .filter(Event.category_chain_overlaps(global_cat.id),
                    ~Event.is_deleted,
                    Event.acl_entries.any(),
                    Event.end_dt >= datetime(2024, 1, 1))
            .options(subqueryload(Event.acl_entries)))
    managers = defaultdict(set)
    managers_by_event = defaultdict(set)
    for event in query:
        if not (evt_managers := {x.user for x in event.acl_entries if x.full_access and x.type == PrincipalType.user}):
            continue
        for user in evt_managers:
            managers[user].add(event)
            managers_by_event[event].add(user)

    for user, events in managers.items():
        group_acls = {
            x.multipass_group_name
            for evt in events
            for x in evt.acl_entries if x.type == PrincipalType.multipass_group
        }

        tpl = get_plugin_template_module('emails/event_notification.txt', name=user.first_name, events=events,
                                         group_acls=group_acls)
        send_email(make_email(to_list={user.email}, template=tpl,
                              sender_address=f'Indico Team <{config.NO_REPLY_EMAIL}>',
                              reply_address='indico-team@cern.ch'))

    for event, users in managers_by_event.items():
        event.log(EventLogRealm.event, LogKind.other, 'Indico Global', 'Sent migration notifications',
                  data={'Recipient IDs': ', '.join(map(str, sorted(u.id for u in users))),
                        'Recipients': ', '.join(sorted(u.full_name for u in users))})

    GlobalRedirectPlugin.settings.set('allow_event_notifications', False)
    db.session.commit()


@cli.command()
def notify_event_managers_zoom():
    """Notify event managers w/ Zoom meetings about upcoming migration."""
    from indico_global_redirect.plugin import GlobalRedirectPlugin

    if not GlobalRedirectPlugin.settings.get('allow_event_notifications_zoom'):
        click.echo('Zoom event notifications are disabled (maybe already sent?)')
        return

    SettingsProxyBase.allow_cache_outside_request = True  # avoid re-querying site_title for every email
    global_cat = Category.get(GlobalRedirectPlugin.settings.get('global_category_id'))
    query = (Event.query
            .filter(Event.category_chain_overlaps(global_cat.id),
                    ~Event.is_deleted,
                    Event.acl_entries.any(),
                    Event.end_dt >= datetime(2025, 1, 18),
                    Event.vc_room_associations.any())
            .options(subqueryload(Event.acl_entries)))
    managers = defaultdict(set)
    managers_by_event = defaultdict(set)
    for event in query:
        if not (evt_managers := {x.user for x in event.acl_entries if x.full_access and x.type == PrincipalType.user}):
            continue
        for user in evt_managers:
            managers[user].add(event)
            managers_by_event[event].add(user)

    for user, events in managers.items():
        tpl = get_plugin_template_module('emails/event_notification_zoom.txt', name=user.first_name, events=events)
        send_email(make_email(to_list={user.email}, template=tpl,
                              sender_address=f'Indico Team <{config.NO_REPLY_EMAIL}>',
                              reply_address='indico-team@cern.ch'))

    for event, users in managers_by_event.items():
        event.log(EventLogRealm.event, LogKind.other, 'Indico Global', 'Sent migration notifications (Zoom)',
                  data={'Recipient IDs': ', '.join(map(str, sorted(u.id for u in users))),
                        'Recipients': ', '.join(sorted(u.full_name for u in users))})

    GlobalRedirectPlugin.settings.set('allow_event_notifications_zoom', False)
    db.session.commit()
