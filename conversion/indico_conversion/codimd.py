# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from sqlalchemy.orm.util import AliasedClass

import indico
from indico.core import signals
from indico.core.config import config
from indico.core.db import db
from indico.core.db.sqlalchemy.util.models import IndicoBaseQuery
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType, LinkType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.categories import Category
from indico.modules.events.contributions import Contribution
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.models.events import Event
from indico.modules.events.sessions import Session
from indico.util.date_time import format_datetime, now_utc
from indico.util.i18n import _


REQUEST_HEADERS = {'User-Agent': f'Indico/{indico.__version__}'}


def _leads_to_auth_page(response: requests.Response) -> bool:
    """Check if the response indicates that authentication is required."""
    # Unfortunately, CodiMD does not provide a specific header for this,
    # so we check for a redirect to the OAuth2 login page.
    return response.status_code == 302 and '/auth/oauth2' in response.headers.get('location', '')


# XXX: TBD during review
# this could probably be moved to the core, since the prometheus plugin also uses something similar?
def build_attachment_query() -> tuple[IndicoBaseQuery, AliasedClass, AliasedClass, AliasedClass]:
    """Build an ORM query which gets all attachments."""
    contrib_event = db.aliased(Event)
    contrib_session = db.aliased(Session)
    subcontrib_contrib = db.aliased(Contribution)
    subcontrib_session = db.aliased(Session)
    subcontrib_event = db.aliased(Event)
    session_event = db.aliased(Event)

    attachment_filter = db.and_(
        ~Attachment.is_deleted,
        ~AttachmentFolder.is_deleted,
        db.or_(
            AttachmentFolder.link_type != LinkType.event,
            ~Event.is_deleted,
        ),
        db.or_(
            AttachmentFolder.link_type != LinkType.contribution, ~Contribution.is_deleted & ~contrib_event.is_deleted
        ),
        db.or_(
            AttachmentFolder.link_type != LinkType.subcontribution,
            db.and_(~SubContribution.is_deleted, ~subcontrib_contrib.is_deleted, ~subcontrib_event.is_deleted),
        ),
        db.or_(AttachmentFolder.link_type != LinkType.session, ~Session.is_deleted & ~session_event.is_deleted),
    )

    return (
        (
            Attachment.query.join(Attachment.folder)
            .outerjoin(AttachmentFolder.linked_event)
            .outerjoin(AttachmentFolder.contribution)
            .outerjoin(Contribution.event.of_type(contrib_event))
            .outerjoin(Contribution.session.of_type(contrib_session))
            .outerjoin(AttachmentFolder.subcontribution)
            .outerjoin(SubContribution.contribution.of_type(subcontrib_contrib))
            .outerjoin(subcontrib_contrib.event.of_type(subcontrib_event))
            .outerjoin(subcontrib_contrib.session.of_type(subcontrib_session))
            .outerjoin(AttachmentFolder.session)
            .outerjoin(Session.event.of_type(session_event))
            .filter(attachment_filter)
            .filter(AttachmentFolder.link_type != LinkType.category)
        ),
        session_event,
        contrib_event,
        subcontrib_event,
    )


def parse_codimd_url(url: str) -> tuple[str, bool] | None:
    """Parse a CodiMD URL and return the document ID and whether it is a published link.

    :param url: The URL to parse
    :return: A tuple of (document_id, is_published) if the URL is valid, None otherwise.
    """
    from indico_conversion.plugin import ConversionPlugin

    if not url or not isinstance(url, str):
        return None

    if not (codimd_base_url := ConversionPlugin.settings.get('codimd_base_url')):
        return None

    # First check, to see if it's worth trying to parse the URL at all
    if not url.startswith(codimd_base_url.rstrip('/')):
        return None

    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        # Check if the base path is present in the URL, and if it is, remove it
        base_path = urlparse(codimd_base_url).path.strip('/')
        if base_path and path.startswith(base_path):
            path = path[len(base_path):].lstrip('/')

        if not path:
            return None

        # either /s/<doc_id> (published) or /<doc_id> (regular)
        path_match = re.match(r'^(?P<published>s/)?(?P<doc_id>[a-zA-Z0-9_-]+)(?:/.*)?$', path)
        if not path_match:
            return None

        doc_id = path_match.group('doc_id')
        is_published = bool(path_match.group('published'))

        return doc_id, is_published

    except (ValueError, AttributeError):
        return None


def find_content_urls(url: str) -> tuple[str, str] | None:
    """Extract the CodiMD document ID from the given URL and return the Markdown and PDF URLs."""
    from indico_conversion.plugin import ConversionPlugin

    codimd_base_url = ConversionPlugin.settings.get('codimd_base_url')

    if not (parsed := parse_codimd_url(url)):
        return None
    else:
        (doc_id, published) = parsed

    if published:
        # this one is a bit tricky, since the published URL endpoint doesn't let you download the PDF
        # so we need to fetch the edit URL first in order to get the download URLs
        try:
            response = requests.get(
                f'{codimd_base_url}/s/{doc_id}/edit', headers=REQUEST_HEADERS, allow_redirects=False
            )
            if response.status_code == 302:
                # this is the edit URL, we can use it to get the download and PDF URLs
                base_url = response.headers['location']
                if _leads_to_auth_page(response):
                    ConversionPlugin.logger.warning('Skipping %s since it seems to be protected', url)
                    return None
            else:
                ConversionPlugin.logger.error(
                    'Error fetching CodiMD edit URL for published page: %d %s', response.status_code, response.text
                )
                return None
        except requests.RequestException as e:
            ConversionPlugin.logger.error('Error fetching CodiMD edit URL for published page: %s', e)
            return None
    else:
        base_url = f'{codimd_base_url}/{doc_id}'
    return (f'{base_url}/download', f'{base_url}/pdf')


def save_file(attachment: Attachment, data: bytes, extension: str, mime_type: str) -> Attachment:
    """Save a file as a new attachment."""
    from indico_conversion.plugin import ConversionPlugin

    with attachment.folder.event.force_event_locale():
        archived_attachment = Attachment(
            folder=attachment.folder,
            user=attachment.user,
            title=f'{attachment.title} ({"PDF" if extension == "pdf" else "Markdown"})',
            description=_('This snapshot was automatically created on {}').format(
                format_datetime(now_utc(), format='short', timezone=config.DEFAULT_TIMEZONE)
            ),
            type=AttachmentType.file,
            protection_mode=attachment.protection_mode,
            acl=attachment.acl,
            converted_from=attachment,
            annotations={
                'source': 'codimd-archiver',
                'archived_on': now_utc().isoformat(),
                'archived_from': attachment.link_url,
            },
        )

        archived_attachment.file = AttachmentFile(
            user=attachment.user, filename=f'archived.{extension}', content_type=mime_type
        )
    archived_attachment.file.save(data)
    db.session.add(archived_attachment)
    db.session.flush()
    ConversionPlugin.logger.info('Added %s attachment %s for %s', extension, archived_attachment, attachment)
    signals.attachments.attachment_created.send(archived_attachment, user=None)
    return archived_attachment


def download_from_url(url: str, mime_type: str) -> bytes | None:
    """Download content from URL, taking into account potential protected content."""
    from indico_conversion.plugin import ConversionPlugin

    ConversionPlugin.logger.info('Getting %s', url)
    response = requests.get(url, headers={**REQUEST_HEADERS, 'Accept': mime_type}, allow_redirects=False)

    if _leads_to_auth_page(response):
        ConversionPlugin.logger.warning('%s seems to be protected', url)
    elif response.status_code == 200:
        return response.content
    else:
        ConversionPlugin.logger.error(
            'Something happened with %s: %s %s', url, response.status_code, response.text
        )
    return None


def archive_candidate_link(link_attachment: Attachment) -> tuple[Attachment, Attachment] | None:
    """Archive candidate link, returning true or false based on success."""
    if not (urls := find_content_urls(link_attachment.link_url)):
        return None

    md_url, pdf_url = urls
    markdown_data = download_from_url(md_url, 'text/markdown')
    pdf_data = download_from_url(pdf_url, 'application/pdf')
    if not markdown_data or not pdf_data:
        return None
    else:
        # we're OK, there are both markdown and PDF
        return (
            save_file(link_attachment, pdf_data, 'pdf', 'application/pdf'),
            save_file(link_attachment, markdown_data, 'md', 'text/markdown'),
        )


def _build_query(min_date: datetime, max_date: datetime, url: str, exclude_category_ids: list[int] | None = None):
    """Build actual DB query to find all link attachments which match the URL."""
    base_query, session_event, contrib_event, subcontrib_event = build_attachment_query()

    query = base_query.filter(
        db.or_(
            (Event.end_dt >= min_date) & (Event.end_dt <= max_date),
            (session_event.end_dt >= min_date) & (session_event.end_dt <= max_date),
            (contrib_event.end_dt >= min_date) & (contrib_event.end_dt <= max_date),
            (subcontrib_event.end_dt >= min_date) & (subcontrib_event.end_dt <= max_date),
        ),
        Attachment.type == AttachmentType.link,
        Attachment.link_url.like(f'{url}/%'),
    )

    # Exclude categories if requested (including their subtrees)
    if exclude_category_ids:
        excluded_cte = Category.get_subtree_ids_cte(exclude_category_ids)
        excluded_ids_subq = db.select([excluded_cte.c.id])
        query = query.filter(
            db.and_(
                db.or_(AttachmentFolder.link_type != LinkType.event, ~Event.category_id.in_(excluded_ids_subq)),
                db.or_(
                    AttachmentFolder.link_type != LinkType.session, ~session_event.category_id.in_(excluded_ids_subq)
                ),
                db.or_(
                    AttachmentFolder.link_type != LinkType.contribution,
                    ~contrib_event.category_id.in_(excluded_ids_subq),
                ),
                db.or_(
                    AttachmentFolder.link_type != LinkType.subcontribution,
                    ~subcontrib_event.category_id.in_(excluded_ids_subq),
                ),
            )
        )

    return query


def _archive_codimd_content(
    start_dt: datetime | None = None,
    exclude_category_ids: list[int] | None = None,
    dry_run: bool = False,
):
    """Archive CodiMD content.

    Args:
        max_age: Maximum age of content to archive (in hours).
        start_dt: Start date (TZ-aware) to include for archival.
        exclude_category_ids: List of category IDs to exclude.
    """
    from indico_conversion.plugin import ConversionPlugin

    base_url = ConversionPlugin.settings.get('codimd_base_url')
    min_age = ConversionPlugin.settings.get('codimd_min_age')

    # get the last archival date from settings
    last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')

    if not start_dt and not last_run_dt:
        ConversionPlugin.logger.warning('No last archival date found, please run the task manually for the first time')
        return

    max_date = now_utc() - timedelta(hours=min_age)
    # subtract the minimum age to avoid gaps in the archival
    min_date = start_dt or last_run_dt - timedelta(hours=min_age)
    ConversionPlugin.logger.info('Looking for candidates between min date: %s, and max date: %s', min_date, max_date)

    query = _build_query(min_date, max_date, base_url, exclude_category_ids)
    candidates = query.all()

    ConversionPlugin.logger.info('Found %d candidate links', len(candidates))

    for candidate in candidates:
        obj = candidate.folder.object
        ConversionPlugin.logger.info('Processing %s (%s)', candidate.link_url, obj)

        # check whether the candidate has already been archived
        if candidate.converted_into and any(
            attachment.annotations.get('source') == 'codimd-archiver' for attachment in candidate.converted_into
        ):
            ConversionPlugin.logger.info('Skipping %s since it has already been archived', candidate.link_url)
            continue

        # try to archive the candidate
        if attachments := archive_candidate_link(candidate):
            # Archival succeeded, log it
            ConversionPlugin.logger.info('Archived %s', attachments)
        else:
            # Archival failed, log it
            ConversionPlugin.logger.info('Skipping %s', candidate.link_url)

    ConversionPlugin.settings.set('codimd_archive_last_run_dt', now_utc())
