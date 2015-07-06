from __future__ import unicode_literals

import base64
import os
import uuid
from io import BytesIO

import requests
from flask import request, jsonify
from itsdangerous import BadData

from indico.core import signals
from indico.core.celery import celery
from indico.core.db import db
from indico.core.plugins import url_for_plugin
from indico.modules.attachments.models.attachments import Attachment, AttachmentType, AttachmentFile
from indico.util.signing import secure_serializer
from MaKaC.webinterface.rh.base import RHSimple

from indico_conversion import cache
from indico_conversion.util import get_pdf_title


@celery.task
def submit_attachment(attachment):
    """Sends an attachment's file to the conversion service"""
    from indico_conversion.plugin import ConversionPlugin
    url = ConversionPlugin.settings.get('server_url')
    payload = {
        'attachment_id': attachment.id
    }
    data = {
        # use random-ish filename because of terrible backend code which fails
        # when two files with the same name are uploaded at the same time...
        'filename': '{}-{}'.format(uuid.uuid4(), attachment.file.filename),
        'converter': 'pdf',
        'urlresponse': url_for_plugin('conversion.callback', _external=True),
        'segnum': '1',
        'lastseg': '1',
        'dirresponse': secure_serializer.dumps(payload, salt='pdf-conversion')
    }
    with attachment.file.open() as fd:
        try:
            response = requests.post(url, data=data, files={'segfile': fd}, timeout=5)
            response.raise_for_status()
            if 'ok' not in response.text:
                raise requests.RequestException('Unexpected response from server: {}'.format(response.text))
        except requests.RequestException:
            ConversionPlugin.logger.exception('Could not submit {} for PDF conversion'.format(attachment))
        else:
            ConversionPlugin.logger.info('Submitted {} for PDF conversion'.format(attachment))


@RHSimple.wrap_function
def conversion_finished():
    from indico_conversion.plugin import ConversionPlugin
    try:
        payload = secure_serializer.loads(request.form['directory'], salt='pdf-conversion')
    except BadData:
        ConversionPlugin.logger.exception('Received invalid payload ({})'.format(request.form['directory']))
        return jsonify(success=False)
    attachment = Attachment.get(payload['attachment_id'])
    if not attachment or attachment.is_deleted or attachment.folder.is_deleted:
        ConversionPlugin.logger.error('Attachment has been deleted: {}'.format(attachment))
        return jsonify(success=True)
    elif request.form['status'] != '1':
        ConversionPlugin.logger.error('Received invalid status {} for {}'.format(request.form['status'], attachment))
        return jsonify(success=False)
    data = BytesIO(base64.decodestring(request.form['content']))
    name, ext = os.path.splitext(attachment.file.filename)
    title = get_pdf_title(attachment)
    pdf_attachment = Attachment(folder=attachment.folder, user=attachment.user, title=title,
                                description=attachment.description, type=AttachmentType.file,
                                protection_mode=attachment.protection_mode, acl=attachment.acl)
    pdf_attachment.file = AttachmentFile(user=attachment.file.user, filename='{}.pdf'.format(name),
                                         content_type='application/pdf')
    pdf_attachment.file.save(data)
    db.session.add(pdf_attachment)
    cache.delete(unicode(attachment.id))
    ConversionPlugin.logger.info('Added PDF attachment {} for {}'.format(pdf_attachment, attachment))
    signals.attachments.attachment_created.send(pdf_attachment, user=None)
    return jsonify(success=True)
