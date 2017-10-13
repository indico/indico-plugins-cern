from __future__ import unicode_literals

from flask import session

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState

from indico_cern_access import _
from indico_cern_access.forms import CERNAccessForm
from indico_cern_access.util import (check_access, is_authorized_user, is_category_blacklisted, update_access_request,
                                     withdraw_event_access_request)


class CERNAccessRequestDefinition(RequestDefinitionBase):
    name = 'cern-access'
    title = _('CERN Visitor Badges')
    form = CERNAccessForm

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['user_authorized'] = is_authorized_user(session.user)
        kwargs['category_blacklisted'] = is_category_blacklisted(event.category)
        return super(CERNAccessRequestDefinition, cls).render_form(event, **kwargs)

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def send(cls, req, data):
        check_access(req)
        super(CERNAccessRequestDefinition, cls).send(req, data)
        update_access_request(req)
        req.state = RequestState.accepted

    @classmethod
    def withdraw(cls, req, notify_event_managers=False):
        check_access(req)
        withdraw_event_access_request(req)
        super(CERNAccessRequestDefinition, cls).withdraw(req, notify_event_managers)
