# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import sys
from operator import itemgetter

import click
import yaml

from indico.cli.core import cli_group
from indico.core.db import db
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
