from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db, PyIntEnum
from indico_cern_access.models.access_requests import AccessRequestState
from sqlalchemy import Boolean


class RegformAccessRequest(db.Model):
    __tablename__ = 'regform_access_requests'
    __table_args__ = {'schema': 'plugin_cern_access'}

    form_id = db.Column(
        db.ForeignKey('event_registration.forms.id'),
        primary_key=True
    )

    request_state = db.Column(
        PyIntEnum(AccessRequestState),
        nullable=False,
        default=AccessRequestState.not_requested
    )

    allow_unpaid = db.Column(
        Boolean,
        nullable=False,
        default=False
    )

    registration_form = db.relationship(
        'RegistrationForm',
        uselist=False,
        lazy=True,
        backref=db.backref('access_request', uselist=False))
