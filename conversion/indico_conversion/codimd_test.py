# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import timedelta

import freezegun
import pytest
import requests
import responses

from indico.modules.attachments.models.attachments import Attachment, AttachmentType, LinkType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.events.sessions.models.sessions import Session
from indico.util.date_time import now_utc

from .codimd import (_archive_codimd_content, archive_candidate_link, build_attachment_query, download_from_url,
                     find_content_urls, parse_codimd_url)
from .plugin import ConversionPlugin


CODIMD_BASE_URL = 'https://codimd.example.com'


@pytest.fixture(autouse=True)
def config_plugin():
    ConversionPlugin.settings.set('codimd_base_url', CODIMD_BASE_URL)
    ConversionPlugin.settings.set('codimd_min_age', 12)


@pytest.mark.usefixtures('db')
def test_parse_codimd_url_unpublished():
    # Test with a valid CodiMD URL
    url = f'{CODIMD_BASE_URL}/abc123'
    assert parse_codimd_url(url) == ('abc123', False)


@pytest.mark.usefixtures('db')
def test_parse_codimd_url_published():
    # Test with a published CodiMD URL
    url = f'{CODIMD_BASE_URL}/s/abc125'
    assert parse_codimd_url(url) == ('abc125', True)


@pytest.mark.usefixtures('db')
def test_parse_codimd_url_invalid():
    # Test with an invalid URL
    url = 'https://example.com/not-codimd'
    assert parse_codimd_url(url) is None


@pytest.mark.usefixtures('db')
def test_find_content_urls_invalid_host_returns_none():
    assert find_content_urls('https://codimd.somewhere.else.ch/1234') is None


@pytest.mark.usefixtures('db')
def test_find_content_urls_unpublished_success():
    # easy use case
    assert find_content_urls(f'{CODIMD_BASE_URL}/123456') == (
        f'{CODIMD_BASE_URL}/123456/download',
        f'{CODIMD_BASE_URL}/123456/pdf',
    )


def test_build_attachment_query_excludes_deleted(db, dummy_event, dummy_user):
    # valid attachment
    folder_ok = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    a_ok = Attachment(
        folder=folder_ok,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/doc-ok',
        title='ok',
    )

    # excluded: attachment is deleted
    a_deleted = Attachment(
        folder=folder_ok,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/doc-deleted',
        title='deleted',
        is_deleted=True,
    )

    # excluded: folder is deleted
    folder_deleted = AttachmentFolder(
        object=dummy_event, link_type=LinkType.event, is_default=False, title='a test', is_deleted=True
    )
    a_folder_deleted = Attachment(
        folder=folder_deleted,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/doc-folder-deleted',
        title='folder-deleted',
    )

    db.session.flush()

    query, _session_event, _contrib_event, _subcontrib_event = build_attachment_query()
    results = query.all()

    assert a_ok in results
    assert a_deleted not in results
    assert a_folder_deleted not in results


def test_find_content_urls_published_success(mocked_responses):
    # simulate the redirection done by CodiMD
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/s/123456/edit',
        status=302,
        headers={'location': f'{CODIMD_BASE_URL}/s/banana-is-h3r3'},
    )

    # published page
    assert find_content_urls(f'{CODIMD_BASE_URL}/s/123456') == (
        f'{CODIMD_BASE_URL}/s/banana-is-h3r3/download',
        f'{CODIMD_BASE_URL}/s/banana-is-h3r3/pdf',
    )


def test_find_content_urls_published_oauth_redirect_returns_none(mocked_responses):
    # same thing, but the resource is protected
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/s/123456/edit',
        status=302,
        headers={'location': 'https://bigsciencelab.org/auth/oauth2'},
    )

    assert find_content_urls(f'{CODIMD_BASE_URL}/s/123456') is None


def test_find_content_urls_published_request_exception_returns_none(mocked_responses):
    # simulate a network/requests exception when fetching the edit URL
    mocked_responses.add(responses.GET, f'{CODIMD_BASE_URL}/s/whatever/edit', body=requests.RequestException())

    assert find_content_urls(f'{CODIMD_BASE_URL}/s/whatever') is None


def test_download_from_url_pdf_500_returns_none(mocked_responses):
    url = f'{CODIMD_BASE_URL}/s/foo/pdf'
    mocked_responses.add(
        responses.GET,
        url,
        headers={'Content-Type': 'application/pdf'},
        status=500,
        body=b'Internal Server Error',
    )
    assert download_from_url(url, 'application/pdf') is None


def test_archive_candidate_link_unpublished_success(db, dummy_event, dummy_user, mocked_responses):
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/xpto1234/download',
        headers={'Content-Type': 'text/markdown'},
        body=b'# ALL HAIL THE PENGUIN GODS\n##who shall reign over the seafood',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/xpto1234/pdf',
        headers={'Content-Type': 'application/pdf'},
        body=b'PDF_CONTENT',
    )

    folder = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    attachment = Attachment(
        folder=folder, type=AttachmentType.link, user=dummy_user, link_url=f'{CODIMD_BASE_URL}/xpto1234', title='test'
    )
    db.session.flush()

    pdf, md = archive_candidate_link(attachment)

    assert md.file.content_type == 'text/markdown'
    assert pdf.file.content_type == 'application/pdf'


def test_archive_candidate_link_published_success(db, dummy_event, dummy_user, mocked_responses):
    # simulate the redirection done by CodiMD for published pages
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/s/123456/edit',
        status=302,
        headers={'location': f'{CODIMD_BASE_URL}/banana-is-h3r3'},
    )

    # mock the final download endpoints
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/banana-is-h3r3/download',
        headers={'Content-Type': 'text/markdown'},
        body=b'# Published note\nSome contents',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/banana-is-h3r3/pdf',
        headers={'Content-Type': 'application/pdf'},
        body=b'PDF_CONTENT',
    )

    folder = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/s/123456',
        title='published test',
    )
    db.session.flush()

    pdf, md = archive_candidate_link(attachment)

    assert md.file.content_type == 'text/markdown'
    assert pdf.file.content_type == 'application/pdf'


def test_archive_candidate_link_pdf_fetch_fails_returns_none(db, dummy_event, dummy_user, mocked_responses):
    # simulate the redirection done by CodiMD for published pages
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/s/123456/edit',
        status=302,
        headers={'location': f'{CODIMD_BASE_URL}/banana-is-h3r3'},
    )

    # markdown succeeds, pdf fails
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/banana-is-h3r3/download',
        headers={'Content-Type': 'text/markdown'},
        body=b'# Published note\nSome contents',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/banana-is-h3r3/pdf',
        headers={'Content-Type': 'application/pdf'},
        status=500,
        body=b'Internal Server Error',
    )

    folder = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/s/123456',
        title='published test pdf',
    )
    db.session.flush()

    result = archive_candidate_link(attachment)

    assert result is None
    # ensure no archived file attachments were created
    assert not any(a for a in folder.all_attachments if a.type == AttachmentType.file)


def test_archive_candidate_link_oauth_redirect_returns_none(db, dummy_event, dummy_user, mocked_responses):
    # simulate the redirection done by CodiMD for published pages
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/s/654321/edit',
        status=302,
        headers={'location': 'https://bigsciencelab.org/auth/oauth2'},
    )

    folder = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/s/654321',
        title='published oauth redirect',
    )
    db.session.flush()

    result = archive_candidate_link(attachment)

    assert result is None
    # ensure no archived file attachments were created
    assert not any(a for a in folder.all_attachments if a.type == AttachmentType.file)


@freezegun.freeze_time(now_utc())
def test_archive_codimd_archival_data_is_updated(db, dummy_event, dummy_user, mocked_responses):
    # create a log entry in settings, to simulate a previous archival run
    ConversionPlugin.settings.set('codimd_archive_last_run_dt', now_utc() - timedelta(hours=24))

    # set the event dates to the period where the link should be archived
    dummy_event.start_dt = now_utc() - timedelta(hours=14)
    dummy_event.end_dt = now_utc() - timedelta(hours=13)

    # mock a CodiMD link
    folder = AttachmentFolder(object=dummy_event, link_type=LinkType.event, is_default=True)
    Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/123456',
        title='test codimd link',
    )
    db.session.flush()

    # mock the CodiMD response
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/123456/download',
        headers={'Content-Type': 'text/markdown'},
        body='# Test Content',
    )

    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/123456/pdf',
        headers={'Content-Type': 'application/pdf'},
        body=b'PDF_CONTENT',
    )

    # archive all links in the given period
    _archive_codimd_content()

    # check that the log data is updated in settings
    last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')
    assert last_run_dt == now_utc()

    attachments = Attachment.query.filter_by(folder=folder, type=AttachmentType.file).all()
    assert len(attachments) == 2
    assert attachments[0].type == AttachmentType.file
    assert attachments[0].file.content_type == 'application/pdf'
    assert attachments[0].file.open().read() == b'PDF_CONTENT'
    assert attachments[0].file.filename == 'archived.pdf'

    assert attachments[1].type == AttachmentType.file
    assert attachments[1].file.content_type == 'text/markdown'
    assert attachments[1].file.open().read() == b'# Test Content'
    assert attachments[1].file.filename == 'archived.md'


def test_archive_codimd_content_no_log_entry_and_no_max_age_returns_none(db, dummy_event, dummy_user, mocked_responses):
    # archive all links in the given period
    _archive_codimd_content()

    # check that no log entry was created in settings
    last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')
    assert last_run_dt is None

    attachments = Attachment.query.filter_by(folder_id=1, type=AttachmentType.file).all()
    assert len(attachments) == 0


def test_build_attachment_query_contribution_links(db, dummy_user, dummy_contribution):
    # Test with contribution link
    folder = AttachmentFolder(object=dummy_contribution, link_type=LinkType.contribution, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/contrib-test',
        title='contrib test',
    )
    db.session.flush()

    query, _session_event, _contrib_event, _subcontrib_event = build_attachment_query()
    results = query.all()
    assert attachment in results


def test_build_attachment_query_subcontribution_links(db, dummy_user, dummy_subcontribution):
    # Test with subcontribution link
    folder = AttachmentFolder(object=dummy_subcontribution, link_type=LinkType.subcontribution, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/subcontrib-test',
        title='subcontrib test',
    )
    db.session.flush()

    query, _session_event, _contrib_event, _subcontrib_event = build_attachment_query()
    results = query.all()
    assert attachment in results


def test_build_attachment_query_session_links(db, dummy_event, dummy_user):
    # Test with session link
    session = Session(event=dummy_event, title='Test Session')
    folder = AttachmentFolder(object=session, link_type=LinkType.session, is_default=True)
    attachment = Attachment(
        folder=folder,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/session-test',
        title='session test',
    )
    db.session.flush()

    query, _session_event, _contrib_event, _subcontrib_event = build_attachment_query()
    results = query.all()
    assert attachment in results


def test_archive_codimd_timing_overlap(db, dummy_user, mocked_responses, create_event):
    """Test that archival timing logic creates proper overlap to prevent gaps."""
    # Configure plugin settings
    ConversionPlugin.settings.set('codimd_min_age', 12)  # 12 hours minimum age
    ConversionPlugin.settings.set('codimd_archive_last_run_dt', now_utc() - timedelta(days=1))

    # Mock CodiMD responses for all requests
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/event1/download',
        headers={'Content-Type': 'text/markdown'},
        body='# Event 1 Content',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/event1/pdf',
        headers={'Content-Type': 'application/pdf'},
        body=b'PDF_EVENT1',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/event2/download',
        headers={'Content-Type': 'text/markdown'},
        body='# Event 2 Content',
    )
    mocked_responses.add(
        responses.GET,
        f'{CODIMD_BASE_URL}/event2/pdf',
        headers={'Content-Type': 'application/pdf'},
        body=b'PDF_EVENT2',
    )

    # Create two events that ended at different times
    # Event 1 ended 15 hours ago (should be archived in first run)
    event_1 = create_event(
        title='Event 1', start_dt=now_utc() - timedelta(hours=16), end_dt=now_utc() - timedelta(hours=15)
    )
    folder_1 = AttachmentFolder(object=event_1, link_type=LinkType.event, is_default=True)
    attachment_1 = Attachment(
        folder=folder_1,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/event1',
        title='Event 1 Link',
    )

    # Event 2 ended 10 hours ago (should be archived in second run due to overlap)
    event_2 = create_event(
        title='Event 2', start_dt=now_utc() - timedelta(hours=11), end_dt=now_utc() - timedelta(hours=10)
    )
    folder_2 = AttachmentFolder(object=event_2, link_type=LinkType.event, is_default=True)
    attachment_2 = Attachment(
        folder=folder_2,
        type=AttachmentType.link,
        user=dummy_user,
        link_url=f'{CODIMD_BASE_URL}/event2',
        title='Event 2 Link',
    )

    db.session.add_all([event_1, folder_1, attachment_1, event_2, folder_2, attachment_2])
    db.session.flush()

    # FIRST RUN: Simulate initial archival run 2 hours ago (N - 2h, where N = now_utc())
    first_run_time = now_utc() - timedelta(hours=2)
    with freezegun.freeze_time(first_run_time):
        # Run archival - should archive event1 which ended 13 hours ago relative to first_run_time (N - 15h)
        _archive_codimd_content()

        # Verify first run settings were updated
        last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')
        assert last_run_dt == first_run_time

        # Verify that event 1 was archived
        archived_attachments = Attachment.query.filter(
            Attachment.type == AttachmentType.file, ~Attachment.is_deleted
        ).all()
        assert archived_attachments[0].annotations['archived_from'] == 'https://codimd.example.com/event1'
        assert archived_attachments[1].annotations['archived_from'] == 'https://codimd.example.com/event1'
        assert len(archived_attachments) == 2  # PDF + MD for event1

    # SECOND RUN: Current time (2 hours later)
    with freezegun.freeze_time(now_utc()):
        # Clear previous file attachments to test second run independently
        Attachment.query.filter(Attachment.type == AttachmentType.file).update({'is_deleted': True})
        db.session.flush()

        # Run archival again
        _archive_codimd_content()

        # Verify timing logic creates overlap:
        # min_date should be: first_run_time - min_age = (N - 2h) - 12h = N - 14h
        # max_date should be: N - min_age = N - 12h
        # Event 2 ended only 10h ago, which is > 12h ago, so it should NOT be archived

        new_archived_attachments = Attachment.query.filter(
            Attachment.type == AttachmentType.file, ~Attachment.is_deleted
        ).all()

        assert len(new_archived_attachments) == 0  # No new archives

        # Verify settings were updated
        last_run_dt = ConversionPlugin.settings.get('codimd_archive_last_run_dt')
        assert last_run_dt == now_utc()

    # THIRD RUN: 5 hours later (N + 5h, event 2 should now be old enough)
    third_run_time = now_utc() + timedelta(hours=5)
    with freezegun.freeze_time(third_run_time):
        # Run archival again
        _archive_codimd_content()

        # Now event 2 (ended 15h ago relative to third_run_time) should be archived
        # min_date = N - 12h
        # max_date = third_run_time - 12h = N + 5h - 12h = N - 7h
        # Event 2 ended 10h ago from original time, which falls in this range

        final_archived_attachments = Attachment.query.filter(
            Attachment.type == AttachmentType.file, ~Attachment.is_deleted
        ).all()
        assert final_archived_attachments[0].annotations['archived_from'] == 'https://codimd.example.com/event2'
        assert final_archived_attachments[1].annotations['archived_from'] == 'https://codimd.example.com/event2'
        assert len(final_archived_attachments) == 2  # PDF + MD for event2
