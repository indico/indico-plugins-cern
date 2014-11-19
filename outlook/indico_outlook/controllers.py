from flask import jsonify

from indico.core.db import db
from MaKaC.webinterface.rh.users import RHUserBase

from indico_outlook.models.blacklist import OutlookBlacklistUser


class RHToggleOutlookBlacklist(RHUserBase):
    """Toggles the calendar synchronization for a user"""

    def _process(self):
        user = self._avatar
        blacklist = OutlookBlacklistUser.find_first(user_id=int(user.id))
        if blacklist:
            db.session.delete(blacklist)
            state = True
        else:
            db.session.add(OutlookBlacklistUser(user=user))
            state = False
        return jsonify(success=True, state=state)
