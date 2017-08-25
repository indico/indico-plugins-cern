from __future__ import unicode_literals

from flask import session
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.events.requests import RequestDefinitionBase, RequestState

from indico_cern_access import _
from indico_cern_access.forms import CERNAccessForm
from indico_cern_access.util import (is_authorized_user, is_category_blacklisted, update_access_request,
                                     withdraw_event_access_request)


class CERNAccessRequestDefinition(RequestDefinitionBase):
    name = 'cern_access'
    title = _('Access to CERN site')
    form = CERNAccessForm

    @classmethod
    def render_form(cls, event, **kwargs):
        kwargs['can_send_request'] = is_authorized_user(session.user)
        kwargs['is_category_blacklisted'] = is_category_blacklisted(event.category)
        return super(CERNAccessRequestDefinition, cls).render_form(event, **kwargs)

    @classmethod
    def can_be_managed(cls, user):
        return False

    @classmethod
    def send(cls, req, data):
        with db.session.no_autoflush:
            user_authorized = is_authorized_user(session.user)
            category_blacklisted = is_category_blacklisted(req.event_new.category)
        if not user_authorized or category_blacklisted:
            raise Forbidden()
        super(CERNAccessRequestDefinition, cls).send(req, data)
        update_access_request(req)
        req.state = RequestState.accepted

    @classmethod
    def withdraw(cls, req, notify_event_managers=False):
        with db.session.no_autoflush:
            user_authorized = is_authorized_user(session.user)
            category_blacklisted = is_category_blacklisted(req.event_new.category)
        if not user_authorized or category_blacklisted:
            raise Forbidden()
        withdraw_event_access_request(req)
        super(CERNAccessRequestDefinition, cls).withdraw(req, notify_event_managers)
