# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from datetime import timedelta

from indico.core import signals
from indico.core.db import db
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType

from indico_conversion import pdf_state_cache


def get_pdf_title(attachment):
    if attachment.type == AttachmentType.link:
        return attachment.title
    # Must be of type file
    ext = os.path.splitext(attachment.file.filename)[1]
    if attachment.title.endswith(ext):
        return attachment.title[:-len(ext)] + '.pdf'
    else:
        return attachment.title


def save_pdf(attachment, pdf):
    from indico_conversion.plugin import ConversionPlugin
    if attachment.type == AttachmentType.file:
        name = os.path.splitext(attachment.file.filename)[0]
    else:
        name = attachment.title
    title = get_pdf_title(attachment)
    pdf_attachment = Attachment(folder=attachment.folder, user=attachment.user, title=title,
                                description=attachment.description, type=AttachmentType.file,
                                protection_mode=attachment.protection_mode, acl=attachment.acl)
    if attachment.type == AttachmentType.file:
        user = attachment.file.user
    else:
        user = attachment.user
    pdf_attachment.file = AttachmentFile(user=user, filename=f'{name}.pdf',
                                         content_type='application/pdf')
    pdf_attachment.file.save(pdf)
    db.session.add(pdf_attachment)
    db.session.flush()
    pdf_state_cache.set(str(attachment.id), 'finished', timeout=timedelta(minutes=15))
    ConversionPlugin.logger.info('Added PDF attachment %s for %s', pdf_attachment, attachment)
    signals.attachments.attachment_created.send(pdf_attachment, user=None)
