# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property

from indico.core.db.sqlalchemy import PyIntEnum, db
from indico.modules.events.registration.fields.accompanying import AccompanyingPerson
from indico.util.enum import RichIntEnum
from indico.util.string import format_repr

from indico_cern_access import _
from indico_cern_access.models.archived_requests import ArchivedCERNAccessRequest


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
        nullable=True,
        unique=True
    )
    adams_nonce = db.Column(
        db.String,
        nullable=False,
        default='',
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
    license_plate = db.Column(
        db.String,
        nullable=True
    )
    accompanying_persons = db.Column(
        JSONB,
        nullable=False,
        default={}
    )

    registration = db.relationship(
        'Registration',
        uselist=False,
        lazy=True,
        backref=db.backref(
            'cern_access_request',
            cascade='all, delete-orphan',
            uselist=False,
            lazy=False
        )
    )

    @hybrid_property
    def is_not_requested(self):
        return self.request_state == CERNAccessRequestState.not_requested

    @hybrid_property
    def is_withdrawn(self):
        return self.request_state == CERNAccessRequestState.withdrawn

    @hybrid_property
    def is_active(self):
        return self.request_state == CERNAccessRequestState.active

    @hybrid_property
    def has_identity_info(self):
        return bool(self.birth_place) and bool(self.nationality) and self.birth_date is not None

    @has_identity_info.expression
    def has_identity_info(cls):
        return cls.birth_place.isnot(None) & cls.nationality.isnot(None) & cls.birth_date.isnot(None)

    @property
    def accompanying_persons_codes(self):
        persons = self.registration.accompanying_persons
        persons_names = {p['id']: AccompanyingPerson(p).display_full_name for p in persons}
        return [{'name': persons_names[id], 'code': data['reservation_code']}
                for id, data in self.accompanying_persons.items()]

    def clear_identity_data(self):
        self.birth_date = None
        self.nationality = None
        self.birth_place = None
        self.license_plate = None
        for person in self.accompanying_persons.values():
            person['license_plate'] = None
        self.accompanying_persons = {id: {k: data[k] for k in ('reservation_code', 'adams_nonce') if k in data}
                                     for id, data in self.accompanying_persons.items()}

    def archive(self):
        db.session.add(ArchivedCERNAccessRequest.create_from_request(self))
        self.registration.cern_access_request = None
        db.session.flush()

    def __repr__(self):
        return format_repr(self, 'registration_id', 'request_state')
