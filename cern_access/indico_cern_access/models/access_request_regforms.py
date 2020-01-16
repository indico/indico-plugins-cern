# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from sqlalchemy.ext.hybrid import hybrid_property

from indico.core.db.sqlalchemy import PyIntEnum, db

from indico_cern_access.models.access_requests import CERNAccessRequestState


class CERNAccessRequestRegForm(db.Model):
    __tablename__ = 'access_request_regforms'
    __table_args__ = {'schema': 'plugin_cern_access'}

    form_id = db.Column(
        db.ForeignKey('event_registration.forms.id'),
        primary_key=True
    )
    request_state = db.Column(
        PyIntEnum(CERNAccessRequestState),
        nullable=False,
        default=CERNAccessRequestState.not_requested
    )

    registration_form = db.relationship(
        'RegistrationForm',
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
