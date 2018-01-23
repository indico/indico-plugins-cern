# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from sqlalchemy.ext.hybrid import hybrid_property

from indico.core.db.sqlalchemy import PyIntEnum, db
from indico.util.struct.enum import RichIntEnum

from indico_cern_access import _


class CERNAccessRequestState(RichIntEnum):
    __titles__ = [_('Not requested'), _('Accepted'), _('Withdrawn')]
    not_requested = 0
    active = 1
    withdrawn = 2


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
    birth_date = db.Column(
        db.Date,
        nullable=True
    )
    nationality = db.Column(
        db.String,
        nullable=True
    )
    birth_place = db.Column(
        db.String,
        nullable=True
    )

    registration = db.relationship(
        'Registration',
        uselist=False,
        lazy=True,
        backref=db.backref(
            'cern_access_request',
            uselist=False,
            lazy=False
        )
    )

    @hybrid_property
    def is_withdrawn(self):
        return self.request_state == CERNAccessRequestState.withdrawn

    @hybrid_property
    def is_active(self):
        return self.request_state == CERNAccessRequestState.active

    @property
    def has_identity_info(self):
        return bool(self.birth_place) and bool(self.nationality) and self.birth_date is not None

    def clear_identity_data(self):
        self.birth_date = None
        self.nationality = None
        self.birth_place = None
