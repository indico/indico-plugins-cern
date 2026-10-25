# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import logging
from datetime import datetime

import click
from sqlalchemy import cast, extract, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import aliased

from indico.cli.core import cli_group
from indico.core.db import db
from indico.modules.attachments.models.attachments import Attachment
from indico.modules.attachments.models.folders import AttachmentFolder

from .codimd import _archive_codimd_content
from .plugin import ConversionPlugin


@cli_group(name='codimd-archival')
def cli():
    """Manage the CodiMD part of the Conversion plugin."""


@cli.command(name='init')
@click.option(
    '--start-dt',
    type=click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M']),
    help='Start date (UTC) to include for archival (default: all)',
)
@click.option(
    '--exclude-category',
    multiple=True,
    type=int,
    help='Exclude a category (and its subtree) by ID. Can be repeated.',
)
@click.option('--force', is_flag=True, help='Run even if archival has already been initialized')
@click.option('--dry-run', is_flag=True, help='Do not commit the changes to the database')
def init_cmd(start_dt: datetime, exclude_categories: list[int], force: bool, dry_run: bool):
    """Trigger an immediate archival of all CodiMD content. This is only meant to be run manually."""
    # refuse to run if archival already happened unless forced
    last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')
    if last_run_dt and not force:
        click.secho(f'Archival already initialized on {last_run_dt}. Use --force to run anyway.', fg='yellow')
        raise SystemExit(1)

    ConversionPlugin.logger = logging.getLogger('codimd-archiver-dry-run')
    ConversionPlugin.logger.setLevel(logging.INFO)
    ConversionPlugin.logger.addHandler(logging.StreamHandler())

    # run synchronously in-process
    _archive_codimd_content(start_dt=start_dt, exclude_category_ids=exclude_categories)
    if dry_run:
        db.session.rollback()
        click.secho('Dry run, changes not committed', fg='yellow')
    else:
        db.session.commit()


@cli.command(name='status')
def status_cmd():
    """Show the last archival date and its log entries."""
    last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')

    if last_run_dt:
        click.secho(f'Last run time: {last_run_dt}', fg='green')
    else:
        click.secho('Last run time: never', fg='yellow')


@cli.command(name='stats')
def stats_cmd():
    """Show some statistics on how many files were archived and when."""
    # Query to group by year with counts
    year_counts = (
        db.session.query(
            extract('year', cast(Attachment.annotations['archived_on'].astext, TIMESTAMP)).label('archived_year'),
            extract('month', cast(Attachment.annotations['archived_on'].astext, TIMESTAMP)).label('archived_month'),
            func.count(func.distinct(Attachment.converted_from_id)).label('attachment_count'),
        )
        .filter(
            Attachment.annotations['source'].astext == 'codimd-archiver',
            Attachment.converted_from_id.isnot(None),
            Attachment.annotations['archived_on'].astext.isnot(None),
        )
        .group_by(
            'archived_year', 'archived_month'
        )
        .order_by('archived_year', 'archived_month')
        .all()
    )

    for year, month, num in year_counts:
        print(f'{int(year)}/{int(month):02}: {num}')

    print(f'\nTotal: {sum(num for _y, _m, num in year_counts)} attachments archived')


@cli.command(name='list')
@click.option(
    '--start-dt',
    type=click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M']),
    help='Start date (UTC) to query',
)
@click.option(
    '--end-dt',
    type=click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M']),
    help='End date (UTC) to query',
)
def list_cmd(start_dt, end_dt):
    """List all archived CodiMD URLs with their Indico attachment IDs and archival dates, in chronological order."""
    original_attachment = aliased(Attachment)

    archived_on = cast(Attachment.annotations['archived_on'].astext, TIMESTAMP)

    query = (
        db.session.query(
            AttachmentFolder,
            func.min(archived_on).label('archived_on'),
            original_attachment.link_url,
            func.count(Attachment.id).label('count'),
        )
        .join(original_attachment, Attachment.converted_from_id == original_attachment.id)
        .join(AttachmentFolder, original_attachment.folder_id == AttachmentFolder.id)
        .filter(
            Attachment.annotations['source'].astext == 'codimd-archiver',
            Attachment.converted_from_id.isnot(None),
            Attachment.annotations['archived_on'].astext.isnot(None),
        )
        .group_by(
            Attachment.converted_from_id,
            AttachmentFolder,
            original_attachment.link_url,
        )
    )

    if start_dt:
        query = query.having(func.min(archived_on) >= start_dt)
    if end_dt:
        query = query.having(func.min(archived_on) <= end_dt)

    results = query.order_by(func.min(archived_on)).all()

    if not results:
        print('No archived CodiMD attachments found for the given dates.')
        return

    for folder, archived_on, url, count in results:
        folder_text = click.style(folder.object.url, fg='yellow')
        print(
            f'{archived_on or "N/A"} {click.style(url, fg='cyan')} {folder_text} {count} attachments'
        )

    print(f'\nTotal: {len(results)} URLs archived')
