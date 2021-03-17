# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import dateutil.parser
from flask import request, session
from sqlalchemy import func
from sqlalchemy.orm import aliased
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.util.date_time import as_utc, get_day_end, get_day_start
from indico.util.iterables import group_list
from indico.web.rh import RHProtected

from indico_room_assistance.forms import RequestListFilterForm
from indico_room_assistance.util import is_room_assistance_support
from indico_room_assistance.views import WPRoomAssistance


def _find_requests(from_dt=None, to_dt=None):
    inner = (Request.query
             .filter(Request.type == 'room-assistance',
                     Request.state == RequestState.accepted)
             .add_columns(func.jsonb_array_elements_text(Request.data['occurrences']).label('requested_at'))
             .subquery())

    aliased_event = aliased(Event, name='event')
    query = db.session.query(inner, aliased_event).join(aliased_event, aliased_event.id == inner.c.event_id)
    if from_dt:
        query = query.filter(db.cast(inner.c.requested_at, db.DateTime) >= from_dt)
    if to_dt:
        query = query.filter(db.cast(inner.c.requested_at, db.DateTime) <= to_dt)
    return [req._asdict() for req in query]


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
            results = group_list(results, key=lambda req: dateutil.parser.parse(req['requested_at']).date(),
                                 sort_by=lambda req: dateutil.parser.parse(req['requested_at']).date(),
                                 sort_reverse=reverse)
            results = dict(sorted(results.items(), reverse=reverse))
        return WPRoomAssistance.render_template('request_list.html', form=form, results=results,
                                                parse_dt=dateutil.parser.parse)
