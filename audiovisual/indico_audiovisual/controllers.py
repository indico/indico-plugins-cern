# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from flask import session

from indico.core.errors import AccessError
from MaKaC.webinterface.rh.base import RHProtected

from indico_audiovisual.util import is_av_manager
from indico_audiovisual.views import WPAudiovisualManagers


class RHRequestList(RHProtected):
    def _checkProtection(self):
        RHProtected._checkProtection(self)
        if self._doProcess and not is_av_manager(session.user):
            raise AccessError

    def _process(self):
        return WPAudiovisualManagers.render_template('request_list.html')
