from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db, PyIntEnum
from indico.util.string import return_ascii
from indico.util.struct.enum import IndicoEnum
from MaKaC.user import AvatarHolder
from MaKaC.conference import ConferenceHolder


class OutlookAction(int, IndicoEnum):
    add = 1
    update = 2
    remove = 3


class OutlookQueueEntry(db.Model):
    """Pending calendar updates"""
    __tablename__ = 'outlook_queue'
    __table_args__ = (db.Index('ix_user_event_action', 'user_id', 'event_id', 'action'),
                      {'schema': 'plugin_outlook'})

    #: Entry ID (mainly used to sort by insertion order)
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    #: ID of the user
    user_id = db.Column(
        db.Integer,
        nullable=False
    )
    #: ID of the event
    event_id = db.Column(
        db.Integer,
        index=True,
        nullable=False
    )
    #: :class:`OutlookAction` to perform
    action = db.Column(
        PyIntEnum(OutlookAction),
        nullable=False
    )

    @property
    def user(self):
        return AvatarHolder().getById(str(self.user_id))

    @user.setter
    def user(self, user):
        self.user_id = int(user.getId())

    @property
    def event(self):
        return ConferenceHolder().getById(str(self.event_id), True)

    @event.setter
    def event(self, event):
        self.event_id = int(event.getId())

    @return_ascii
    def __repr__(self):
        return '<OutlookQueueEntry({}, {}, {}, {})>'.format(self.id, self.event_id, self.user_id,
                                                            OutlookAction(self.action).name)

    @classmethod
    def record(cls, event, user, action):
        """Records a new calendar action

        :param event: the event (a `Conference` instance)
        :param user: the user (an `Avatar` instance)
        :param action: the action (an `OutlookAction`)
        """
        try:
            event_id = int(event.id)
            user_id = int(user.id)
        except ValueError:
            return
        if AvatarHolder().getById(user.id) is None:
            return
        # We delete a possible existing item first so the new one is inserted at the end
        cls.find(event_id=event_id, user_id=user_id, action=action).delete()
        db.session.add(cls(event_id=event_id, user_id=user_id, action=action))
        db.session.flush()
