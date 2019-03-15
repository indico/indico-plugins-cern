# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from collections import OrderedDict

import dateutil.parser
from flask import request, session
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.util.date_time import as_utc, get_day_end, get_day_start
from indico.util.struct.iterables import group_list
from indico.web.rh import RHProtected

from indico_room_assistance.forms import RequestListFilterForm
from indico_room_assistance.util import is_room_assistance_support
from indico_room_assistance.views import WPRoomAssistance


def _find_requests(from_dt=None, to_dt=None):
    query = (Request.query
             .options(joinedload(Request.event))
             .filter(Request.type == 'room-assistance',
                     Request.state == RequestState.accepted,
                     db.cast(Request.data, postgresql.JSONB).has_key('start_dt')))  # noqa

    if from_dt:
        query = query.filter(db.cast(Request.data['start_dt'].astext, db.DateTime) >= from_dt)
    if to_dt:
        query = query.filter(db.cast(Request.data['start_dt'].astext, db.DateTime) <= to_dt)
    return query.all()


class RHRequestList(RHProtected):
    """Provides a list of videoconference assistance requests"""

    def _check_access(self):
        RHProtected._check_access(self)
        if not is_room_assistance_support(session.user):
            raise Forbidden

    def _process(self):
        form = RequestListFilterForm(request.args)
        results = None
        if form.validate_on_submit():
            reverse = form.direction.data == 'desc'
            from_dt = as_utc(get_day_start(form.start_date.data)) if form.start_date.data else None
            to_dt = as_utc(get_day_end(form.end_date.data)) if form.end_date.data else None
            results = _find_requests(from_dt=from_dt, to_dt=to_dt)
            results = group_list(results, lambda req: dateutil.parser.parse(req.data['start_dt']).date(),
                                 sort_reverse=reverse)
            results = OrderedDict(sorted(results.viewitems(), reverse=reverse))
        return WPRoomAssistance.render_template('request_list.html', form=form, results=results,
                                                parse_dt=dateutil.parser.parse)
