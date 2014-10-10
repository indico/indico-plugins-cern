from __future__ import unicode_literals

from indico.core.db.sqlalchemy import db
from indico.util.string import return_ascii
from MaKaC.user import AvatarHolder


class OutlookBlacklistUser(db.Model):
    """Users who have disabled calendar entries for events"""
    __tablename__ = 'outlook_blacklist'
    __table_args__ = {'schema': 'plugin_outlook'}

    #: ID of the user
    user_id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=False
    )

    @property
    def user(self):
        return AvatarHolder().getById(str(self.user_id))

    @user.setter
    def user(self, user):
        self.user_id = int(user.getId())

    @return_ascii
    def __repr__(self):
        return '<OutlookBlacklistUser({})>'.format(self.user_id)
