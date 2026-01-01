# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.db.sqlalchemy import PyIntEnum, db
from indico.util.enum import IndicoIntEnum
from indico.util.string import format_repr


class OutlookAction(IndicoIntEnum):
    add = 1
    update = 2
    remove = 3


class OutlookQueueEntry(db.Model):
    """Pending calendar updates"""

    __tablename__ = 'queue'
    __table_args__ = (db.Index(None, 'user_id', 'event_id', 'action'),
                      db.CheckConstraint(f'(action != {OutlookAction.update}) OR (category_id IS NULL)',
                                         name='no_category_updates'),
                      db.CheckConstraint('(event_id IS NULL) != (category_id IS NULL)', name='event_xor_category'),
                      {'schema': 'plugin_outlook'})

    #: Entry ID (mainly used to sort by insertion order)
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: ID of the user - may be None if an entry is not user-specific
    user_id = db.Column(
        db.ForeignKey('users.users.id'),
        index=True,
        nullable=True,
    )
    #: ID of the event
    event_id = db.Column(
        db.ForeignKey('events.events.id'),
        index=True,
        nullable=True
    )
    #: ID of the category, in case of a favorite category addition/removal
    category_id = db.Column(
        db.ForeignKey('categories.categories.id'),
        index=True,
        nullable=True,
    )
    #: :class:`OutlookAction` to perform
    action = db.Column(
        PyIntEnum(OutlookAction),
        nullable=False
    )

    #: The user associated with the queue entry
    user = db.relationship(
        'User',
        lazy=False,
        backref=db.backref(
            'outlook_queue',
            lazy='dynamic'
        )
    )
    #: The Event this queue entry is associated with
    event = db.relationship(
        'Event',
        lazy=True,
        backref=db.backref(
            'outlook_queue_entries',
            lazy='dynamic'
        )
    )
    #: The Category this queue entry is associated with
    category = db.relationship(
        'Category',
        lazy=True,
        backref=db.backref(
            'outlook_queue_entries',
            lazy='dynamic'
        )
    )

    def __repr__(self):
        action = OutlookAction(self.action).name
        return format_repr(self, 'event_id', 'category_id', 'user_id', _text=action)

    @classmethod
    def record(cls, event_or_category, user, action):
        """Record a new calendar action."""
        # It would be nice to delete matching records first, but this sometimes results in very weird deadlocks
        event_or_category.outlook_queue_entries.append(cls(user=user, action=action))
        db.session.flush()
