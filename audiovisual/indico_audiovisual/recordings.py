# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re

from marshmallow import ValidationError

from indico.core import signals
from indico.core.db import db
from indico.core.db.sqlalchemy.links import LinkType
from indico.modules.attachments.models.attachments import Attachment, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.sessions.models.sessions import Session


RECORDING_TITLE = 'Recording'
RECORDING_THUMBNAIL_SUFFIX = '/files/frame-1.jpg'


def parse_indico_id(indico_id):
    event_match = re.match(r'(\d+)$', indico_id)
    session_match = re.match(r'(\d+)s(\d+)$', indico_id)
    contrib_match = re.match(r'(\d+)c(\d+)$', indico_id)
    subcontrib_match = re.match(r'(\d+)c(\d+)sc(\d+)$', indico_id)

    if subcontrib_match:
        event = Event.get(subcontrib_match.group(1), is_deleted=False)
        if not event:
            return None
        return (SubContribution.query
                .filter(SubContribution.id == subcontrib_match.group(3),
                        ~SubContribution.is_deleted,
                        SubContribution.contribution.has(event=event, id=subcontrib_match.group(2), is_deleted=False))
                .first())
    elif session_match:
        event = Event.get(session_match.group(1), is_deleted=False)
        return Session.query.with_parent(event).filter_by(id=session_match.group(2)).first()
    elif contrib_match:
        event = Event.get(contrib_match.group(1), is_deleted=False)
        return Contribution.query.with_parent(event).filter_by(id=contrib_match.group(2)).first()
    elif event_match:
        return Event.get(event_match.group(1), is_deleted=False)
    else:
        return None


def parse_indico_id_verbose(indico_id):
    rv = parse_indico_id(indico_id)
    if not rv:
        raise ValidationError('Invalid object identifier')
    return rv


def cds_link_exists(obj, url):
    query = (Attachment.query
             .filter(~Attachment.is_deleted,
                     ~AttachmentFolder.is_deleted,
                     AttachmentFolder.object == obj,
                     Attachment.type == AttachmentType.link,
                     Attachment.link_url == url)
             .join(AttachmentFolder))
    return db.session.query(query.exists()).scalar()


def get_recording_thumbnail_url(link_url):
    return link_url.rstrip('/') + RECORDING_THUMBNAIL_SUFFIX


def get_recording_url_prefix():
    from indico_audiovisual.plugin import AVRequestsPlugin

    url = AVRequestsPlugin.settings.get('recording_cds_url')
    return url.partition('{cds_id}')[0] if url else None


def get_recordings(event, user):
    prefix = get_recording_url_prefix()
    if not prefix:
        return None, []
    attachments = (Attachment.query
                   .filter(~Attachment.is_deleted,
                           ~AttachmentFolder.is_deleted,
                           AttachmentFolder.event_id == event.id,
                           Attachment.type == AttachmentType.link,
                           Attachment.title == RECORDING_TITLE,
                           Attachment.link_url.startswith(prefix))
                   .join(AttachmentFolder)
                   .all())
    accessible = [x for x in attachments if x.can_access(user)]
    event_recordings = [x for x in accessible if x.folder.link_type == LinkType.event]
    inner_recordings = [x for x in accessible if x.folder.link_type != LinkType.event]
    return (event_recordings[0] if event_recordings else None), inner_recordings


def create_link(indico_id, cds_id, user):
    from indico_audiovisual.plugin import AVRequestsPlugin

    obj = parse_indico_id(indico_id)
    if obj is None:
        return False

    url = AVRequestsPlugin.settings.get('recording_cds_url')
    if not url:
        return False

    url = url.format(cds_id=cds_id)
    if cds_link_exists(obj, url):
        return True

    folder = AttachmentFolder.get_or_create_default(obj)
    attachment = Attachment(folder=folder, user=user, title=RECORDING_TITLE, type=AttachmentType.link, link_url=url)
    db.session.add(attachment)
    db.session.flush()
    signals.attachments.attachment_created.send(attachment, user=user)
    return True
