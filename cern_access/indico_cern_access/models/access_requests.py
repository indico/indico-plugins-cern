from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db, PyIntEnum
from indico.util.struct.enum import RichIntEnum

from indico_cern_access import _


class AccessRequestState(RichIntEnum):
    __titles__ = [_('Not requested'), _('Pending'), _('Accepted'), _('Rejected')]
    not_requested = 0
    pending = 1
    accepted = 2
    rejected = 3


class AccessRequest(db.Model):
    __tablename__ = 'access_requests'
    __table_args__ = {'schema': 'plugin_cern_access'}

    registration_id = db.Column(
        db.ForeignKey('event_registration.registrations.id'),
        primary_key=True
    )

    request_state = db.Column(
        PyIntEnum(AccessRequestState),
        nullable=False,
        default=AccessRequestState.not_requested
    )

    reservation_code = db.Column(
        db.String,
        nullable=False
    )

    registration = db.relationship(
        'Registration',
        uselist=False,
        lazy=True,
        backref=db.backref('access_request', uselist=False))
