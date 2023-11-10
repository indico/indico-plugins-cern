# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from sqlalchemy.dialects.postgresql import JSONB

from indico.core.db import db
from indico.util.string import format_repr


class ArchivedCERNAccessRequest(db.Model):
    __tablename__ = 'archived_access_requests'
    __table_args__ = {'schema': 'plugin_cern_access'}

    id = db.Column(
        db.Integer,
        primary_key=True
    )
    event_id = db.Column(
        db.ForeignKey('events.events.id'),
        nullable=False,
        index=True
    )
    # NOT an FK on purpose as the registration may get deleted
    registration_id = db.Column(
        db.Integer,
        nullable=False
    )
    email = db.Column(
        db.String,
        nullable=False,
    )
    first_name = db.Column(
        db.String,
        nullable=False,
    )
    last_name = db.Column(
        db.String,
        nullable=False,
    )
    birth_date = db.Column(
        db.Date,
        nullable=False
    )
    nationality = db.Column(
        db.String,
        nullable=False
    )
    birth_place = db.Column(
        db.String,
        nullable=False
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

    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref(
            'archived_cern_access_requests',
            lazy=True
        )
    )

    @classmethod
    def create_from_request(cls, req):
        return cls(
            event=req.registration.event,
            registration_id=req.registration.id,
            email=req.registration.email,
            first_name=req.registration.first_name,
            last_name=req.registration.last_name,
            birth_date=req.birth_date,
            nationality=req.nationality,
            birth_place=req.birth_place,
            license_plate=req.license_plate,
            accompanying_persons=req.accompanying_persons,
        )

    def __repr__(self):
        return format_repr(self, 'id', 'event_id', registration_id=None, _text=self.email)
