# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from datetime import timedelta
from urllib.parse import urlparse

import dateutil.parser
import requests
from celery.exceptions import MaxRetriesExceededError, Retry
from celery.schedules import crontab
from flask import jsonify, request, session
from itsdangerous import BadData

from indico.core import signals
from indico.core.celery import celery
from indico.core.config import config
from indico.core.db import db
from indico.core.notifications import make_email, send_email
from indico.core.plugins import url_for_plugin
from indico.modules.attachments.models.attachments import Attachment
from indico.util.date_time import now_utc
from indico.util.fs import secure_filename
from indico.util.signing import secure_serializer
from indico.web.flask.templating import get_template_module
from indico.web.flask.util import url_for
from indico.web.rh import RH

from indico_conversion import cloudconvert_task_cache, pdf_state_cache
from indico_conversion.cloudconvert import CloudConvertRestClient
from indico_conversion.util import save_pdf


MAX_TRIES = 20
DELAYS = [30, 60, 120, 300, 600, 1800, 3600, 3600, 7200]


def retry_task(task, attachment, exception):
    from indico_conversion.plugin import ConversionPlugin

    attempt = task.request.retries + 1
    try:
        delay = DELAYS[task.request.retries] if not config.DEBUG else 1
    except IndexError:
        # like this we can safely bump MAX_TRIES manually if necessary
        delay = DELAYS[-1]
    try:
        task.retry(countdown=delay, max_retries=(MAX_TRIES - 1))
    except MaxRetriesExceededError:
        response_text = exception.response.text if exception.response else '<no response>'
        ConversionPlugin.logger.error('Could not submit attachment %d (attempt %d/%d); giving up [%s]: %s',
                                      attachment.id, attempt, MAX_TRIES, exception, response_text)
        pdf_state_cache.delete(str(attachment.id))
    except Retry:
        response_text = exception.response.text if exception.response else '<no response>'
        ConversionPlugin.logger.warning('Could not submit attachment %d (attempt %d/%d); retry in %ds [%s]: %s',
                                        attachment.id, attempt, MAX_TRIES, delay, exception, response_text)
        raise


@celery.task(bind=True, max_retries=None)
def submit_attachment_doconverter(task, attachment):
    """Send an attachment's file to the Doconverter conversion service."""
    from indico_conversion.plugin import ConversionPlugin
    if ConversionPlugin.settings.get('maintenance'):
        task.retry(countdown=900)
    url = ConversionPlugin.settings.get('server_url')
    payload = {
        'attachment_id': attachment.id
    }
    data = {
        'converter': 'pdf',
        'urlresponse': url_for_plugin('conversion.doconverter_callback', _external=True),
        'dirresponse': secure_serializer.dumps(payload, salt='pdf-conversion')
    }
    file = attachment.file
    name, ext = os.path.splitext(file.filename)
    # we know ext is safe since it's based on a whitelist. the name part may be fully
    # non-ascii so we sanitize that to a generic name if necessary
    filename = secure_filename(name, 'attachment') + ext
    with file.open() as fd:
        try:
            response = requests.post(url, data=data, files={'uploadedfile': (filename, fd, file.content_type)})
            response.raise_for_status()
            if 'ok' not in response.text:
                raise requests.RequestException(f'Unexpected response from server: {response.text}', response=response)
        except requests.RequestException as exc:
            retry_task(task, attachment, exc)
        else:
            ConversionPlugin.logger.info('Submitted %r to Doconverter', attachment)


@celery.task(bind=True, max_retries=None)
def request_pdf_from_googledrive(task, attachment):
    """Use the Google Drive API to convert a Google Drive file to a PDF."""
    from indico_conversion.plugin import ConversionPlugin

    # Google drive URLs have this pattern: https://docs.google.com/<TYPE>/d/<FILEID>[/edit]
    try:
        parsed_url = urlparse(attachment.link_url)
        if parsed_url.netloc != 'docs.google.com':
            raise ValueError('Not a google docs URL')
        file_id = parsed_url.path.split('/')[3]
    except (ValueError, IndexError) as exc:
        ConversionPlugin.logger.warning('Could not parse URL %s: %s', attachment.link_url, exc)
        return

    # use requests to get the file from this URL:
    mime_type = 'application/pdf'
    api_key = ConversionPlugin.settings.get('googledrive_api_key')
    request_text = f'https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={mime_type}'
    try:
        response = requests.get(request_text, headers={'x-goog-api-key': api_key})
    except requests.HTTPError as exc:
        if exc.response.status_code == 404:
            ConversionPlugin.logger.warning('Google Drive file %s not found', attachment.link_url)
            pdf_state_cache.delete(str(attachment.id))
            return
        retry_task(task, attachment, exc)
    else:
        content_type = response.headers['Content-type']
        if content_type.startswith('application/json'):
            payload = response.json()
            try:
                error_code = payload['error']['code']
            except (TypeError, KeyError):
                error_code = 0
            if error_code == 404:
                ConversionPlugin.logger.info('Google Drive file %s not found (or not public)', attachment.link_url)
            else:
                ConversionPlugin.logger.warning('Google Drive file %s could not be converted: %s', attachment.link_url,
                                                payload)
            pdf_state_cache.delete(str(attachment.id))
            return
        elif content_type != 'application/pdf':
            ConversionPlugin.logger.warning('Google Drive file %s conversion response is not a PDF: %s',
                                            attachment.link_url, content_type)
            pdf_state_cache.delete(str(attachment.id))
            return
        pdf = response.content
        save_pdf(attachment, pdf)
        signals.core.after_process.send()
        db.session.commit()


class RHDoconverterFinished(RH):
    """Callback to attach a converted file."""

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
            ConversionPlugin.logger.info('Attachment has been deleted: %s', attachment)
            return jsonify(success=True)
        elif request.form['status'] != '1':
            ConversionPlugin.logger.error('Received invalid status %s for %s', request.form['status'], attachment)
            return jsonify(success=False)
        pdf = request.files['content'].stream.read()
        save_pdf(attachment, pdf)
        return jsonify(success=True)


@celery.task(bind=True, max_retries=None)
def submit_attachment_cloudconvert(task, attachment):
    """Send an attachment's file to the CloudConvert conversion service."""
    from indico_conversion.plugin import ConversionPlugin
    if ConversionPlugin.settings.get('maintenance'):
        task.retry(countdown=900)

    api_key = ConversionPlugin.settings.get('cloudconvert_api_key')
    sandbox = ConversionPlugin.settings.get('cloudconvert_sandbox')
    client = CloudConvertRestClient(api_key=api_key, sandbox=sandbox)

    import_task = f'import-file-{attachment.id}'
    convert_task = f'convert-file-{attachment.id}'
    export_task = f'export-file-{attachment.id}'
    signed_id = secure_serializer.dumps(attachment.id, salt='pdf-conversion')

    job_definition = {
        'tag': f'{attachment.id}__{signed_id}',
        'tasks': {
            import_task: {
                'operation': 'import/upload',
            },
            convert_task: {
                'operation': 'convert',
                'input': import_task,
                'output_format': 'pdf',
            },
            export_task: {
                'operation': 'export/url',
                'input': convert_task
            }
        },
        'webhook_url': url_for_plugin('conversion.cloudconvert_callback', _external=True)
    }

    try:
        job = client.Job.create(payload=job_definition)
        upload_task = job['tasks'][0]
        export_task = job['tasks'][-1]
        assert upload_task['operation'] == 'import/upload'
        assert export_task['operation'] == 'export/url'
        with attachment.file.open() as fd:
            client.Task.upload(upload_task, attachment.file.filename, fd, attachment.file.content_type)
        # add polling in case we miss a webhook
        export_task_id = export_task['id']
        cloudconvert_task_cache.set(export_task_id, 'pending')
        check_attachment_cloudconvert.apply_async(args=(attachment.id, export_task_id), countdown=15)
    except requests.RequestException as exc:
        retry_task(task, attachment, exc)
    else:
        ConversionPlugin.logger.info('Submitted %r to CloudConvert', attachment)


@celery.task(bind=True, max_retries=None)
def check_attachment_cloudconvert(task, attachment_id, export_task_id):
    from indico_conversion.plugin import ConversionPlugin

    api_key = ConversionPlugin.settings.get('cloudconvert_api_key')
    sandbox = ConversionPlugin.settings.get('cloudconvert_sandbox')
    client = CloudConvertRestClient(api_key=api_key, sandbox=sandbox)
    status = cloudconvert_task_cache.get(export_task_id, '<unknown>')

    if status == 'done':
        ConversionPlugin.logger.info('Converted file for attachment %d (task %s) already received via webhook',
                                     attachment_id, export_task_id)
        return
    elif status == 'failed':
        ConversionPlugin.logger.info('Converted file for attachment %d (task %s) already failed via webhook',
                                     attachment_id, export_task_id)
        return
    elif status == 'processing':
        ConversionPlugin.logger.info('Converted file for attachment %d (task %s) already being processed via webhook',
                                     attachment_id, export_task_id)
        task.retry(countdown=30)  # retry the task in case something fails during the webhook though
        return
    elif status != 'pending':
        ConversionPlugin.logger.warning('Unexpected conversion state for attachment %d (task %s): %s',
                                        attachment_id, export_task_id, status)
        return

    try:
        export_task = client.Task.find(export_task_id)
    except requests.RequestException:
        task.retry(countdown=30)
        return

    if export_task['status'] == 'error':
        ConversionPlugin.logger.warning('Conversion for attachment %d (task %s) failed (%s)',
                                        attachment_id, export_task_id, export_task['code'])
        pdf_state_cache.delete(str(attachment_id))
        return
    if export_task['status'] != 'finished':
        ConversionPlugin.logger.info('Conversion for attachment %d (task %s) not finished yet (%s)',
                                     attachment_id, export_task_id, export_task['status'])
        task.retry(countdown=30)
        return

    if (now_utc() - dateutil.parser.parse(export_task['ended_at'])) < timedelta(seconds=10):
        # it's possible that the webhook and task run at the same time, and in that case we
        # want to avoid duplicate files, so we never process the file if it *just* finished
        ConversionPlugin.logger.info('Got successful conversion for attachment %d (task %s) via polling, waiting a bit',
                                     attachment_id, export_task_id)
        task.retry(countdown=5)

    ConversionPlugin.logger.warning('Got successful conversion for attachment %d (task %s) via polling',
                                    attachment_id, export_task_id)
    url = export_task['result']['files'][0]['url']
    attachment = Attachment.get(attachment_id)
    if not attachment or attachment.is_deleted or attachment.folder.is_deleted:
        ConversionPlugin.logger.info('Attachment has been deleted: %s', attachment)
        cloudconvert_task_cache.delete(export_task_id)
        return
    resp = requests.get(url)
    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        response_text = exc.response.text if exc.response else '<no response>'
        ConversionPlugin.logger.warning('Could not download converted file for attachment %d (task %s): %s [%s]',
                                        attachment_id, export_task_id, exc, response_text)
        task.retry(countdown=60)
        return
    save_pdf(attachment, resp.content)
    signals.core.after_process.send()
    cloudconvert_task_cache.delete(export_task_id)
    db.session.commit()


class RHCloudConvertFinished(RH):
    """Callback to attach a converted file."""

    CSRF_ENABLED = False

    def _process(self):
        from indico_conversion.plugin import ConversionPlugin

        event = request.json['event']
        job = request.json['job']
        task = [t for t in job['tasks'] if t['operation'] == 'export/url'][0]

        try:
            signed_id = job['tag'].split('__', 1)[1]
            attachment_id = secure_serializer.loads(signed_id, salt='pdf-conversion')
        except (IndexError, BadData):
            ConversionPlugin.logger.exception('Received invalid payload (%s)', job['tag'])
            return jsonify(success=False)

        if event == 'job.failed':
            ConversionPlugin.logger.error('CloudConvert conversion job failed: %s', request.json)
            cloudconvert_task_cache.set(task['id'], 'failed', 3600)
            pdf_state_cache.delete(str(attachment_id))
            return jsonify(success=False)

        attachment = Attachment.get(attachment_id)
        if not attachment or attachment.is_deleted or attachment.folder.is_deleted:
            ConversionPlugin.logger.info('Attachment has been deleted: %s', attachment)
            cloudconvert_task_cache.set(task['id'], 'done', 3600)
            return jsonify(success=True)

        # make sure polling task doesn't also process the file in case of a race condition
        cloudconvert_task_cache.set(task['id'], 'processing', 3600)

        try:
            url = task['result']['files'][0]['url']
            resp = requests.get(url)
            try:
                resp.raise_for_status()
            except requests.RequestException as exc:
                response_text = exc.response.text if exc.response else '<no response>'
                ConversionPlugin.logger.error('Could not download converted file for attachment %d (task %s): %s [%s]',
                                              attachment_id, task['id'], exc, response_text)
                return jsonify(success=False)

            save_pdf(attachment, resp.content)
        except Exception:
            # if anything goes wrong here give the polling task a chance to succeed
            cloudconvert_task_cache.set(task['id'], 'pending', 3600)
            raise
        cloudconvert_task_cache.set(task['id'], 'done', 3600)
        return jsonify(success=True)


class RHConversionCheck(RH):
    """Checks if all conversions have finished"""

    def _process(self):
        ids = request.args.getlist('a')
        results = {int(id_): pdf_state_cache.get(id_) for id_ in ids}
        finished = [id_ for id_, status in results.items() if status == 'finished']
        pending = [id_ for id_, status in results.items() if status == 'pending']
        containers = {}
        if finished:
            tpl = get_template_module('attachments/_display.html')
            for attachment in Attachment.query.filter(Attachment.id.in_(finished)):
                if not attachment.folder.can_view(session.user):
                    continue
                containers[attachment.id] = tpl.render_attachments_folders(item=attachment.folder.object)
        return jsonify(finished=finished, pending=pending, containers=containers)


@celery.periodic_task(bind=True, max_retries=3, run_every=crontab(minute='0', hour='2'))
def check_cloudconvert_credits(task):
    from indico_conversion.plugin import ConversionPlugin

    if not ConversionPlugin.settings.get('use_cloudconvert'):
        return

    api_key = ConversionPlugin.settings.get('cloudconvert_api_key')
    client = CloudConvertRestClient(api_key=api_key, sandbox=False)
    notify_threshold = ConversionPlugin.settings.get('cloudconvert_notify_threshold')
    notify_email = ConversionPlugin.settings.get('cloudconvert_notify_email')

    if notify_threshold is None:
        return

    try:
        credits = client.get_remaining_credits()
    except requests.RequestException as err:
        ConversionPlugin.logger.info('Could not fetch the remaining CloudConvert credits: %s', err)
        task.retry(countdown=1800)

    if credits < notify_threshold:
        ConversionPlugin.logger.warning('CloudConvert credits below configured threshold; current value: %s', credits)
        if notify_email:
            plugin_settings_url = url_for('plugins.details', plugin=ConversionPlugin.name, _external=True)
            template = get_template_module('conversion:emails/cloudconvert_low_credits.html', credits=credits,
                                           plugin_settings_url=plugin_settings_url)
            email = make_email(to_list=notify_email, template=template, html=True)
            send_email(email)
    else:
        ConversionPlugin.logger.info('CloudConvert credits: %s', credits)
