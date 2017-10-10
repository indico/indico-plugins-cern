from __future__ import unicode_literals

import base64
import os
from datetime import timedelta
from io import BytesIO

import requests
from celery.exceptions import MaxRetriesExceededError, Retry
from flask import jsonify, request, session
from itsdangerous import BadData

from indico.core import signals
from indico.core.celery import celery
from indico.core.config import config
from indico.core.db import db
from indico.core.plugins import url_for_plugin
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType
from indico.util.signing import secure_serializer
from indico.web.flask.templating import get_template_module
from indico.web.rh import RH

from indico_conversion import cache
from indico_conversion.util import get_pdf_title


MAX_TRIES = 10
DELAYS = [30, 60, 120, 300, 600, 1800, 3600, 3600, 7200]


@celery.task(bind=True, max_retries=None)
def submit_attachment(task, attachment):
    """Sends an attachment's file to the conversion service"""
    from indico_conversion.plugin import ConversionPlugin
    if ConversionPlugin.settings.get('maintenance'):
        task.retry(countdown=900)
    url = ConversionPlugin.settings.get('server_url')
    payload = {
        'attachment_id': attachment.id
    }
    data = {
        'converter': 'pdf',
        'urlresponse': url_for_plugin('conversion.callback', _external=True),
        'dirresponse': secure_serializer.dumps(payload, salt='pdf-conversion')
    }
    with attachment.file.open() as fd:
        try:
            response = requests.post(url, data=data, files={'uploadedfile': fd}, verify=False)
            response.raise_for_status()
            if 'ok' not in response.text:
                raise requests.RequestException('Unexpected response from server: {}'.format(response.text))
        except requests.RequestException as exc:
            attempt = task.request.retries + 1
            delay = (DELAYS + [0])[task.request.retries] if not config.DEBUG else 1
            try:
                task.retry(countdown=delay, max_retries=(MAX_TRIES - 1))
            except MaxRetriesExceededError:
                ConversionPlugin.logger.error('Could not submit attachment %d (attempt %d/%d); giving up [%s]',
                                              attachment.id, attempt, MAX_TRIES, exc)
                cache.delete(unicode(attachment.id))
            except Retry:
                ConversionPlugin.logger.warning('Could not submit attachment %d (attempt %d/%d); retry in %ds [%s]',
                                                attachment.id, attempt, MAX_TRIES, delay, exc)
                raise
        else:
            ConversionPlugin.logger.info('Submitted %r', attachment)


class RHConversionFinished(RH):
    """Callback to attach a converted file"""

    CSRF_ENABLED = False

    def _process(self):
        from indico_conversion.plugin import ConversionPlugin
        try:
            payload = secure_serializer.loads(request.form['directory'], salt='pdf-conversion')
        except BadData:
            ConversionPlugin.logger.exception('Received invalid payload (%s)', request.form['directory'])
            return jsonify(success=False)
        attachment = Attachment.get(payload['attachment_id'])
        if not attachment or attachment.is_deleted or attachment.folder.is_deleted:
            ConversionPlugin.logger.warning('Attachment has been deleted: %s', attachment)
            return jsonify(success=True)
        elif request.form['status'] != '1':
            ConversionPlugin.logger.error('Received invalid status %s for %s', request.form['status'], attachment)
            return jsonify(success=False)
        name, ext = os.path.splitext(attachment.file.filename)
        title = get_pdf_title(attachment)
        pdf_attachment = Attachment(folder=attachment.folder, user=attachment.user, title=title,
                                    description=attachment.description, type=AttachmentType.file,
                                    protection_mode=attachment.protection_mode, acl=attachment.acl)
        # TODO: remove first case when Conversion Server is fully on new version
        if 'content' in request.form:
            # handling of legacy API
            data = BytesIO(base64.decodestring(request.form['content']))
        else:
            filepdf = request.files['content']
            data = filepdf.stream.read()
        pdf_attachment.file = AttachmentFile(user=attachment.file.user, filename='{}.pdf'.format(name),
                                             content_type='application/pdf')
        pdf_attachment.file.save(data)
        db.session.add(pdf_attachment)
        db.session.flush()
        cache.set(unicode(attachment.id), 'finished', timedelta(minutes=15))
        ConversionPlugin.logger.info('Added PDF attachment %s for %s', pdf_attachment, attachment)
        signals.attachments.attachment_created.send(pdf_attachment, user=None)
        return jsonify(success=True)


class RHConversionCheck(RH):
    """Checks if all conversions have finished"""

    def _process(self):
        ids = request.args.getlist('a')
        results = {int(id_): cache.get(id_) for id_ in ids}
        finished = [id_ for id_, status in results.iteritems() if status == 'finished']
        pending = [id_ for id_, status in results.iteritems() if status == 'pending']
        containers = {}
        if finished:
            tpl = get_template_module('attachments/_display.html')
            for attachment in Attachment.find(Attachment.id.in_(finished)):
                if not attachment.folder.can_view(session.user):
                    continue
                containers[attachment.id] = tpl.render_attachments_folders(item=attachment.folder.object)
        return jsonify(finished=finished, pending=pending, containers=containers)
