# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import logging
import re
import sys
from collections import defaultdict
from logging import StreamHandler

import click
import oracledb

from indico.cli.core import cli_group
from indico.modules.users.util import get_user_by_email
from indico.util.console import cformat

from indico_foundationsync.sync import FoundationSync


@cli_group(name='foundationsync')
def cli():
    """Manage the Foundationsync plugin."""


@cli.command()
@click.option('--room', '-r', 'room_name', metavar='ROOM', help="Synchronize only a given room (e.g. '513 R-055')")
@click.option('--dry-run', '-n', is_flag=True, help='Do not commit the changes to the database')
def run(room_name: str | None, dry_run):
    """Synchronize rooms with the CERN Foundation Database"""
    from indico_foundationsync.plugin import FoundationSyncPlugin
    dsn = FoundationSyncPlugin.settings.get('connection_string')
    if not dsn:
        print('Foundation DB connection string is not set')
        sys.exit(1)

    # Support bld/floor-number style room names:
    if room_name:
        room_name = room_name.replace('/', ' ', 1)

    # Log to stdout
    handler = StreamHandler()
    handler.setLevel(logging.INFO)
    FoundationSyncPlugin.logger.addHandler(handler)
    FoundationSync(dsn, FoundationSyncPlugin.logger).run_all(room_name, dry_run=dry_run)


@cli.command()
@click.argument('location')
def spacemanagers(location):
    if not (match := re.match(r'(?P<building>[^/]+)(?:[/ ](?P<floor>[^-]+)(?:-(?P<room_number>.+))?)?', location)):
        print('Invalid location, must be something like `28`, `28/S or `28/S-029`')
        sys.exit(1)
    for i, (room, managers) in enumerate(sorted(_get_space_managers(**match.groupdict()).items())):
        if i > 0:
            print()
        print(cformat('%{white!}Space Managers for %{yellow!}%s%{reset}') % room)
        for email in sorted(managers):
            if user := get_user_by_email(email):
                print(cformat('%{green}%s%{reset} <%{green!}%s%{reset}>') % (user.full_name, email))
            else:
                print(cformat('<%{green!}%s%{reset}>') % email)


def _get_space_managers(building, floor, room_number) -> dict[str, set]:
    from indico_foundationsync.plugin import FoundationSyncPlugin

    filters = {'building': building, 'floor': floor, 'room_number': room_number}
    params = {k: v for k, v in filters.items() if v}
    criteria = ' AND '.join(f'{k.upper()} = :{k}' for k in params)

    with (
        oracledb.connect(FoundationSyncPlugin.settings.get('connection_string'), config_dir='/etc') as conn,
        conn.cursor() as cursor,
    ):
        cursor.execute(f'SELECT * FROM aispub.app_indico_space_managers WHERE {criteria}', **params)  # noqa: S608
        managers = defaultdict(set)
        for row in cursor:
            row = dict(zip([d[0].lower() for d in cursor.description], row, strict=True))
            managers[f'{row['building']}/{row['floor']}-{row['room_number']}'].add(row['email'])
        return dict(managers)
