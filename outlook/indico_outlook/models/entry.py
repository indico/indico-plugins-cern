# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from typing import Self

from indico.core.db.sqlalchemy import db
from indico.util.string import format_repr


class OutlookCalendarEntry(db.Model):
    """Calendar entries that have been created on Outlook."""

    __tablename__ = 'entries'
    __table_args__ = {'schema': 'plugin_outlook'}

    #: ID of the user
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.users.id'),
        index=True,
        primary_key=True,
    )
    #: ID of the event
    event_id = db.Column(
        db.Integer,
        db.ForeignKey('events.events.id'),
        index=True,
        primary_key=True,
    )
    #: ID of the calentar entry, needed to update/delete
    calendar_entry_id = db.Column(
        db.String,
        nullable=False,
    )

    #: The User associated with the calendary entry
    user = db.relationship(
        'User',
        lazy=False,
        backref=db.backref(
            'outlook_calendar_entries',
            lazy='dynamic'
        )
    )
    #: The Event associated with the calendar entry
    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref(
            'outlook_calendar_entries',
            lazy='dynamic'
        )
    )

    def __repr__(self):
        return format_repr(self, 'event_id', 'user_id', _text=self.calendar_entry_id)

    @classmethod
    def get(cls, event, user) -> Self | None:
        """Get the calendar entry ID for a given event and user."""
        return super().get((user.id, event.id))

    @classmethod
    def create(cls, event, user, calendar_id: str):
        """Store the calendar ID for an event and user."""
        entry = cls(event=event, user=user, calendar_entry_id=calendar_id)
        db.session.add(entry)
