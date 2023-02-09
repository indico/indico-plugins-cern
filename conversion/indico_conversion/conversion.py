# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os

import requests
from celery.exceptions import MaxRetriesExceededError, Retry
from celery.schedules import crontab
from flask import jsonify, request, session
from itsdangerous import BadData

from indico.core.celery import celery
from indico.core.config import config
from indico.core.notifications import make_email, send_email
from indico.core.plugins import url_for_plugin
from indico.modules.attachments.models.attachments import Attachment
from indico.util.fs import secure_filename
from indico.util.signing import secure_serializer
from indico.web.flask.templating import get_template_module
from indico.web.flask.util import url_for
from indico.web.rh import RH

from indico_conversion import pdf_state_cache
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
        ConversionPlugin.logger.error('Could not submit attachment %d (attempt %d/%d); giving up [%s]',
                                      attachment.id, attempt, MAX_TRIES, exception)
        pdf_state_cache.delete(str(attachment.id))
    except Retry:
        ConversionPlugin.logger.warning('Could not submit attachment %d (attempt %d/%d); retry in %ds [%s]',
                                        attachment.id, attempt, MAX_TRIES, delay, exception)
        raise


@celery.task(bind=True, max_retries=None)
def submit_attachment_doconverter(task, attachment):
    """Sends an attachment's file to the Doconvert conversion service"""
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
                raise requests.RequestException(f'Unexpected response from server: {response.text}')
        except requests.RequestException as exc:
            retry_task(task, attachment, exc)
        else:
            ConversionPlugin.logger.info('Submitted %r to Doconverter', attachment)


class RHDoconverterFinished(RH):
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
            ConversionPlugin.logger.info('Attachment has been deleted: %s', attachment)
            return jsonify(success=True)
        elif request.form['status'] != '1':
            ConversionPlugin.logger.error('Received invalid status %s for %s', request.form['status'], attachment)
            return jsonify(success=False)
        pdf = request.files['content'].stream.read()
        save_pdf(attachment, pdf)
        return jsonify(success=True)


@celery.task(bind=True, max_retries=3)
def submit_attachment_cloudconvert(task, attachment):
    """Sends an attachment's file to the CloudConvert conversion service"""
    from indico_conversion.plugin import ConversionPlugin
    if ConversionPlugin.settings.get('maintenance'):
        task.retry(countdown=900)

    api_key = ConversionPlugin.settings.get('cloudconvert_api_key')
    sandbox = ConversionPlugin.settings.get('sandbox')
    client = CloudConvertRestClient(api_key=api_key, sandbox=sandbox)

    job_definition = {
        'tag': secure_serializer.dumps(str(attachment.id), salt='pdf-conversion'),
        'tasks': {
            'import-my-file': {
                'operation': 'import/upload',
            },
            'convert-my-file': {
                'operation': 'convert',
                'input': 'import-my-file',
                'output_format': 'pdf',
            },
            'export-my-file': {
                'operation': 'export/url',
                'input': 'convert-my-file'
            }
        },
        'webhook_url': url_for_plugin('conversion.cloudconvert_callback', _external=True)
    }

    try:
        job = client.Job.create(payload=job_definition)
        upload_task_id = job['tasks'][0]['id']
        task = client.Task.find(id=upload_task_id)
        client.Task.upload(task, attachment.file)
    except requests.RequestException as exc:
        retry_task(task, attachment, exc)
    else:
        ConversionPlugin.logger.info('Submitted %r to CloudConvert', attachment)


class RHCloudConvertFinished(RH):
    """Callback to attach a converted file"""

    CSRF_ENABLED = False

    def _process(self):
        from indico_conversion.plugin import ConversionPlugin

        event = request.json['event']
        if event == 'job.failed':
            ConversionPlugin.logger.error('CloudConvert conversion job failed: %s', request.json)
            return jsonify(success=False)

        job = request.json['job']
        task = [t for t in job['tasks'] if t['name'] == 'export-my-file'][0]
        url = task['result']['files'][0]['url']

        try:
            payload = secure_serializer.loads(job['tag'], salt='pdf-conversion')
        except BadData:
            ConversionPlugin.logger.exception('Received invalid payload (%s)', job['tag'])
            return jsonify(success=False)

        attachment_id = int(payload)
        attachment = Attachment.get(attachment_id)
        if not attachment or attachment.is_deleted or attachment.folder.is_deleted:
            ConversionPlugin.logger.info('Attachment has been deleted: %s', attachment)
            return jsonify(success=True)

        save_pdf(attachment, requests.get(url).content)
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


@celery.periodic_task(bind=True, max_retries=None, run_every=crontab(minute='0', hour='2'))
def check_cloudconvert_credits(task):
    from indico_conversion.plugin import ConversionPlugin

    api_key = ConversionPlugin.settings.get('cloudconvert_api_key')
    client = CloudConvertRestClient(api_key=api_key, sandbox=False)
    notify_threshold = ConversionPlugin.settings.get('notify_threshold')
    notify_email = ConversionPlugin.settings.get('notify_email')

    if notify_threshold is None:
        return

    try:
        credits = client.get_remaining_credits()
    except requests.RequestException as err:
        ConversionPlugin.logger.info('Could not fetch the remaining CloudConvert credits: %s', err)
        task.retry(countdown=60)

    if credits <= notify_threshold:
        ConversionPlugin.logger.info('CloudConvert credits are below configured threshold; current value: %s', credits)
        if notify_email:
            plugin_settings_url = url_for('plugins.details', plugin=ConversionPlugin.name, _external=True)
            template = get_template_module('conversion:emails/cloudconvert_low_credits.html', credits=credits,
                                           plugin_settings_url=plugin_settings_url)
            email = make_email(to_list=notify_email, template=template, html=True)
            send_email(email)
