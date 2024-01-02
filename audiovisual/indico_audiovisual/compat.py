# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import redirect, request
from werkzeug.exceptions import NotFound

from indico.core.plugins import IndicoPluginBlueprint
from indico.modules.events.agreements.models.agreements import Agreement
from indico.web.flask.util import url_for

from indico_audiovisual.definition import AVRequest, SpeakerReleaseAgreement


compat_blueprint = IndicoPluginBlueprint('compat_audiovisual', 'indico_audiovisual')


@compat_blueprint.route('/event/<int:event_id>/collaboration/agreement')
def redirect_old_agreement_url(event_id):
    uuid = request.args['authKey']
    agreement = Agreement.query.filter_by(event_id=event_id, uuid=uuid).first()
    if agreement is None:
        raise NotFound
    return redirect(url_for('agreements.agreement_form', event_id=event_id, id=agreement.id, uuid=uuid))


@compat_blueprint.route('/export/eAgreements/<int:event_id>.<ext>')
def redirect_old_eagreement_api(event_id, ext):
    path = f'agreements/{SpeakerReleaseAgreement.name}/{event_id}.{ext}'
    if 'signature' in request.args:
        args = request.args.to_dict()
        for key in ('signature', 'apikey', 'ak', 'timestamp'):
            args.pop(key, None)
        url = url_for('api.httpapi', prefix='export', path=path, _external=True, **args)
        return f'Please use the new URL: {url}', 400
    return redirect(url_for('api.httpapi', prefix='export', path=path, **request.args.to_dict()))


@compat_blueprint.route('/export/video/<any(webcast,recording,"webcast-recording","recording-webcast"):service>.<ext>')
def redirect_old_requests_api(service, ext):
    path = f'{AVRequest.name}.{ext}'
    args = request.args.to_dict()
    services = service.split('-')
    if set(services) != {'webcast', 'recording'}:
        args['service'] = services
    if 'signature' in request.args:
        for key in ('signature', 'apikey', 'ak', 'timestamp'):
            args.pop(key, None)
        url = url_for('api.httpapi', prefix='export', path=path, _external=True, **args)
        return f'Please use the new URL: {url}', 400
    return redirect(url_for('api.httpapi', prefix='export', path=path, **args))
