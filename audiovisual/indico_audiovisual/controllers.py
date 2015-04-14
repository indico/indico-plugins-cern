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

from collections import OrderedDict
from operator import itemgetter

from flask import session, request

from indico.core.errors import AccessError
from indico.util.date_time import get_day_start, get_day_end, as_utc
from indico.util.struct.iterables import group_list
from MaKaC.webinterface.rh.base import RHProtected

from indico_audiovisual.forms import RequestListFilterForm
from indico_audiovisual.util import is_av_manager, find_requests
from indico_audiovisual.views import WPAudiovisualManagers


class RHRequestList(RHProtected):
    """Provides a list of webcast/recording requests"""

    def _checkProtection(self):
        RHProtected._checkProtection(self)
        if self._doProcess and not is_av_manager(session.avatar):
            raise AccessError

    def _process(self):
        form = RequestListFilterForm(request.args)
        results = None
        if request.args and form.validate():
            reverse = form.direction.data == 'desc'
            talks = form.granularity.data == 'talks'
            from_dt = as_utc(get_day_start(form.start_date.data)) if form.start_date.data else None
            to_dt = as_utc(get_day_end(form.end_date.data)) if form.end_date.data else None
            states = {form.state.data} if form.state.data is not None else None
            results = find_requests(talks=talks, from_dt=from_dt, to_dt=to_dt, states=states)
            if not talks:
                results = [(req, req.event, req.event.getStartDate()) for req in results]
            results = group_list(results, lambda x: x[2].date(), itemgetter(2), sort_reverse=reverse)
            results = OrderedDict(sorted(results.viewitems(), key=itemgetter(0), reverse=reverse))

        return WPAudiovisualManagers.render_template('request_list.html', form=form, results=results)
