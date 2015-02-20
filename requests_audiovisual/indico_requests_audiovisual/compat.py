from __future__ import unicode_literals

from flask import request, redirect
from werkzeug.exceptions import NotFound

from indico.core.plugins import IndicoPluginBlueprint
from indico.modules.events.agreements.models.agreements import Agreement
from indico.web.flask.util import url_for

from indico_requests_audiovisual.definition import SpeakerReleaseAgreement, AVRequest


compat_blueprint = IndicoPluginBlueprint('compat_requests_audiovisual', 'indico_requests_audiovisual')


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
    return redirect(url_for('api.httpapi', prefix='export', path=path, **request.args.to_dict()))


@compat_blueprint.route('/export/video/<any(webcast,recording,"webcast-recording","recording-webcast"):service>.<ext>')
def redirect_old_requests_api(service, ext):
    path = '{}.{}'.format(AVRequest.name, ext)
    args = request.args.to_dict()
    services = service.split('-')
    if set(services) != {'webcast', 'recording'}:
        args['service'] = services
    return redirect(url_for('api.httpapi', prefix='export', path=path, **args))
