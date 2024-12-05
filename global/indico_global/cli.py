# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import sys
from collections import defaultdict
from operator import itemgetter

import click
import yaml
from sqlalchemy.orm import subqueryload, undefer

from indico.cli.core import cli_group
from indico.core.db import db
from indico.core.db.sqlalchemy.principals import PrincipalType
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.core.settings import SettingsProxyBase
from indico.modules.categories import Category
from indico.util.console import verbose_iterator

from indico_global.models.id_map import GlobalIdMap


@cli_group(name='global')
def cli():
    """Manage the Global plugin."""


@cli.command()
@click.argument('mapping_file', type=click.File())
def load_mapping(mapping_file):
    """Import the ID mapping from YAML."""
    if GlobalIdMap.query.has_rows():
        click.secho('Mapping table is not empty', fg='yellow')
        if not click.confirm('Continue anyway?'):
            sys.exit(1)

    click.echo('Loading mapping data (this take take a while)...')
    mapping = yaml.safe_load(mapping_file)
    for col, data in mapping.items():
        click.echo(f'Processing {col}...')
        for local_id, global_id in verbose_iterator(data.items(), len(data), get_id=itemgetter(0)):
            GlobalIdMap.create(col, local_id, global_id)

    click.echo('Import finished, committing data...')
    db.session.commit()


@cli.command()
def notify_category_managers():
    """Notify category managers about upcoming migration."""
    from indico_global.plugin import GlobalPlugin

    SettingsProxyBase.allow_cache_outside_request = True  # avoid re-querying site_title for every email
    global_cat = Category.get(GlobalPlugin.settings.get('global_category_id'))
    query = (global_cat.deep_children_query
            .filter(~Category.is_deleted, Category.acl_entries.any())
            .options(subqueryload(Category.acl_entries), undefer('chain_titles')))
    managers = defaultdict(set)
    for cat in query:
        if not (cat_managers := {x.user for x in cat.acl_entries if x.full_access and x.type == PrincipalType.user}):
            continue
        for user in cat_managers:
            managers[user].add(cat)

    for user, cats in managers.items():
        group_acls = {
            x.multipass_group_name
            for cat in cats
            for x in cat.acl_entries if x.type == PrincipalType.multipass_group
        }
        tpl = get_plugin_template_module('emails/cat_notification.txt', name=user.first_name, categories=cats,
                                         group_acls=group_acls)
        send_email(make_email(to_list={user.email}, template=tpl))
