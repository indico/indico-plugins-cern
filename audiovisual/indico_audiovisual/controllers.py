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
from indico.util.iterables import group_list
from indico.web.rh import RHProtected

from indico_audiovisual.forms import RequestListFilterForm
from indico_audiovisual.util import find_requests, is_av_manager
from indico_audiovisual.views import WPAudiovisualManagers


class RHRequestList(RHProtected):
    """Provides a list of webcast/recording requests"""

    def _check_access(self):
        RHProtected._check_access(self)
        if not is_av_manager(session.user):
            raise Forbidden

    def _process(self):
        form = RequestListFilterForm(request.args, csrf_enabled=False)
        results = None
        if request.args and form.validate():
            reverse = form.direction.data == 'desc'
            talks = form.granularity.data == 'talks'
            from_dt = as_utc(get_day_start(form.start_date.data)) if form.start_date.data else None
            to_dt = as_utc(get_day_end(form.end_date.data)) if form.end_date.data else None
            states = {form.state.data} if form.state.data is not None else None
            results = find_requests(talks=talks, from_dt=from_dt, to_dt=to_dt, states=states)
            if not talks:
                results = [(req, req.event, req.event.start_dt) for req in results]
            results = group_list(results, lambda x: x[2].date(), itemgetter(2), sort_reverse=reverse)
            results = OrderedDict(sorted(results.items(), key=itemgetter(0), reverse=reverse))

        return WPAudiovisualManagers.render_template('request_list.html', form=form, results=results)
