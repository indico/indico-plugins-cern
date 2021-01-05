# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import OrderedDict
from operator import itemgetter

from flask import request, session
from werkzeug.exceptions import Forbidden

from indico.util.date_time import as_utc, get_day_end, get_day_start
from indico.util.struct.iterables import group_list
from indico.web.flask.util import url_for
from indico.web.rh import RHProtected

from indico_vc_assistance.forms import RequestListFilterForm
from indico_vc_assistance.util import (find_requests, get_vc_capable_rooms, is_vc_support,
                                       start_time_within_working_hours)
from indico_vc_assistance.views import WPVCAssistance


class RHRequestList(RHProtected):
    """Provides a list of videoconference assistance requests"""

    def _check_access(self):
        RHProtected._check_access(self)
        if not is_vc_support(session.user):
            raise Forbidden

    def _process(self):
        form = RequestListFilterForm(request.args, csrf_enabled=False)
        results = None
        if form.validate_on_submit():
            reverse = form.direction.data == 'desc'
            from_dt = as_utc(get_day_start(form.start_date.data)) if form.start_date.data else None
            to_dt = as_utc(get_day_end(form.end_date.data)) if form.end_date.data else None
            results = find_requests(from_dt=from_dt, to_dt=to_dt)
            results = [(req, req.event, req.event.start_dt, contribs, session_blocks)
                       for req, contribs, session_blocks in results]
            results = group_list(results, lambda x: x[2].date(), itemgetter(2), sort_reverse=reverse)
            results = OrderedDict(sorted(results.items(), key=itemgetter(0), reverse=reverse))
        return WPVCAssistance.render_template('request_list.html', form=form, results=results,
                                              action=url_for('.request_list'), vc_capable_rooms=get_vc_capable_rooms(),
                                              within_working_hours=start_time_within_working_hours)
