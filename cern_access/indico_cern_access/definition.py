from __future__ import unicode_literals


from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState, Request

from indico_cern_access import _
from indico_cern_access.forms import CernAccessForm
from indico_cern_access.util import withdraw_access_request, update_access_request


class CernAccessRequest(RequestDefinitionBase):
    name = 'cern_access'
    title = _('CERN access')
    form = CernAccessForm
    modifiable = True

    @classmethod
    def render_form(cls, **kwargs):
        return super(CernAccessRequest, cls).render_form(**kwargs)

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def send(cls, req, data):
        super(CernAccessRequest, cls).send(req, data)
        req.state = update_access_request(req)

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        req.state = RequestState.withdrawn
        withdraw_access_request(req)
