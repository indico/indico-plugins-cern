# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import redirect, request
from werkzeug.exceptions import NotFound

from indico.core.plugins import IndicoPluginBlueprint
from indico.modules.events.agreements.models.agreements import Agreement
from indico.web.flask.util import url_for

from indico_audiovisual.definition import AVRequest, SpeakerReleaseAgreement


compat_blueprint = IndicoPluginBlueprint('compat_audiovisual', 'indico_audiovisual')


@compat_blueprint.route('/event/<int:confId>/collaboration/agreement')
def redirect_old_agreement_url(confId):
    uuid = request.args['authKey']
    agreement = Agreement.find_first(event_id=confId, uuid=uuid)
    if agreement is None:
        raise NotFound
    return redirect(url_for('agreements.agreement_form', confId=confId, id=agreement.id, uuid=uuid))


@compat_blueprint.route('/export/eAgreements/<event_id>.<ext>')
def redirect_old_eagreement_api(event_id, ext):
    path = 'agreements/{}/{}.{}'.format(SpeakerReleaseAgreement.name, event_id, ext)
    if 'signature' in request.args:
        args = request.args.to_dict()
        for key in ('signature', 'apikey', 'ak', 'timestamp'):
            args.pop(key, None)
        url = url_for('api.httpapi', prefix='export', path=path, _external=True, **args)
        return 'Please use the new URL: {}'.format(url), 400
    return redirect(url_for('api.httpapi', prefix='export', path=path, **request.args.to_dict()))


@compat_blueprint.route('/export/video/<any(webcast,recording,"webcast-recording","recording-webcast"):service>.<ext>')
def redirect_old_requests_api(service, ext):
    path = '{}.{}'.format(AVRequest.name, ext)
    args = request.args.to_dict()
    services = service.split('-')
    if set(services) != {'webcast', 'recording'}:
        args['service'] = services
    if 'signature' in request.args:
        for key in ('signature', 'apikey', 'ak', 'timestamp'):
            args.pop(key, None)
        url = url_for('api.httpapi', prefix='export', path=path, _external=True, **args)
        return 'Please use the new URL: {}'.format(url), 400
    return redirect(url_for('api.httpapi', prefix='export', path=path, **args))
