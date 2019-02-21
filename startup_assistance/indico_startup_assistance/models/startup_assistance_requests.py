# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db
from indico.util.string import format_repr


class StartupAssistanceRequest(db.Model):
    """Startup assistance requests"""

    __tablename__ = 'startup_assistance_requests'
    __table_args__ = {'schema': 'plugin_startup_assistance'}

    reservation_id = db.Column(
        db.ForeignKey('roombooking.reservations.id'),
        primary_key=True
    )

    reservation = db.relationship(
        'Reservation',
        uselist=False,
        lazy=False,
        backref=db.backref(
            'startup_assistance_request',
            uselist=False,
            lazy=True
        )
    )

    def __repr__(self):
        return format_repr(self, 'reservation_id')
