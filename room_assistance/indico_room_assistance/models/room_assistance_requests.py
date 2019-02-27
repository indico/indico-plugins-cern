# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db
from indico.util.string import format_repr


class RoomAssistanceRequest(db.Model):
    """Room assistance requests"""

    __tablename__ = 'room_assistance_requests'
    __table_args__ = {'schema': 'plugin_room_assistance'}

    reservation_id = db.Column(
        db.ForeignKey('roombooking.reservations.id'),
        primary_key=True
    )

    reason = db.Column(
        db.String,
        nullable=False
    )

    reservation = db.relationship(
        'Reservation',
        uselist=False,
        lazy=False,
        backref=db.backref(
            'room_assistance_request',
            cascade='all, delete-orphan',
            uselist=False,
            lazy=True
        )
    )

    def __repr__(self):
        return format_repr(self, 'reservation_id')
