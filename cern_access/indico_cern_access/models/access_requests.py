from __future__ import unicode_literals

from sqlalchemy.ext.hybrid import hybrid_property

from indico.core.db.sqlalchemy import PyIntEnum, db
from indico.util.struct.enum import RichIntEnum

from indico_cern_access import _


class CERNAccessRequestState(RichIntEnum):
    __titles__ = [_('Not requested'), _('Accepted'), _('Rejected'), _('Withdrawn')]
    not_requested = 0
    accepted = 1
    rejected = 2
    withdrawn = 3


class CERNAccessRequest(db.Model):
    __tablename__ = 'access_requests'
    __table_args__ = {'schema': 'plugin_cern_access'}

    registration_id = db.Column(
        db.ForeignKey('event_registration.registrations.id'),
        primary_key=True
    )

    request_state = db.Column(
        PyIntEnum(CERNAccessRequestState),
        nullable=False,
        default=CERNAccessRequestState.not_requested
    )

    reservation_code = db.Column(
        db.String,
        nullable=False
    )

    registration = db.relationship(
        'Registration',
        uselist=False,
        lazy=False,
        backref=db.backref(
            'cern_access_request',
            uselist=False
        )
    )

    @hybrid_property
    def is_active(self):
        return self.request_state != CERNAccessRequestState.withdrawn

    @hybrid_property
    def is_accepted(self):
        return self.request_state == CERNAccessRequestState.accepted
