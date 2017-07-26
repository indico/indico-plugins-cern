from __future__ import unicode_literals

import requests
from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db
from indico.modules.events.registration.models.registrations import Registration
from indico.util import json

from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState
from indico_cern_access.plugin import CERNAccessPlugin
from indico_cern_access.util import add_access_requests, build_access_request_data


@celery.periodic_task(run_every=crontab(minute=0, hour='*/1'), plugin='cern_access')
def resend_access_requests():
    registrations = (Registration.query
                     .join(CERNAccessRequest)
                     .filter(Registration.cern_access_request,
                             CERNAccessRequest.is_active,
                             CERNAccessRequest.request_state != CERNAccessRequestState.accepted)
                     .all())
    data = {registration.id: build_access_request_data(registration, registration.event_new, update=True)
            for registration in registrations}
    headers = {'content-type': 'Application/JSON'}
    json_data = json.dumps([data[key] for key in data])
    r = requests.post(CERNAccessPlugin.settings.get('adams_url'), data=json_data, headers=headers)
    state = (CERNAccessRequestState.accepted
             if r.status_code == requests.codes.ok
             else CERNAccessRequestState.rejected)
    add_access_requests(registrations, data, state)
    db.session.commit()
