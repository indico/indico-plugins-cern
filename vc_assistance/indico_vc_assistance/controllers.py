# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from io import BytesIO
from operator import itemgetter

import icalendar
from flask import request, session
from marshmallow import validate
from webargs import fields
from werkzeug.exceptions import Forbidden

from indico.util.date_time import as_utc, get_day_end, get_day_start, now_utc
from indico.util.iterables import group_list
from indico.util.marshmallow import RelativeDayDateTime
from indico.web.args import use_kwargs
from indico.web.flask.util import send_file, url_for
from indico.web.rh import RHProtected, allow_signed_url
from indico.web.util import jsonify_data, jsonify_form, signed_url_for_user

from indico_vc_assistance import _
from indico_vc_assistance.api import _ical_serialize_vc, _serialize_obj
from indico_vc_assistance.forms import RequestCalendarForm, RequestListFilterForm
from indico_vc_assistance.util import (find_requests, get_vc_capable_rooms, is_vc_support,
                                       start_time_within_working_hours)
from indico_vc_assistance.views import WPVCAssistance


class RHVCSupportProtected(RHProtected):
    def _check_access(self):
        RHProtected._check_access(self)
        if not is_vc_support(session.user):
            raise Forbidden


class RHRequestList(RHVCSupportProtected):
    """Provides a list of videoconference assistance requests"""

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
            results = dict(sorted(results.items(), key=itemgetter(0), reverse=reverse))

        calendar_link = session.pop('vc_assistance_calendar_link_url', None)
        return WPVCAssistance.render_template('request_list.html', form=form, results=results,
                                              action=url_for('.request_list'), vc_capable_rooms=get_vc_capable_rooms(),
                                              within_working_hours=start_time_within_working_hours,
                                              calendar_link_supported=True, calendar_link=calendar_link)


@allow_signed_url
class RHRequestCalendar(RHVCSupportProtected):
    """Provides a calendar of videoconference assistance requests"""

    @use_kwargs({
        'alarm': fields.Int(load_default=0, validate=validate.Range(min=0)),
        'start_dt': RelativeDayDateTime(data_key='start_date', required=True),
        'end_dt': RelativeDayDateTime(data_key='end_date', day_end=True, required=True),
    }, location='query')
    def _process(self, alarm, start_dt, end_dt):
        results = find_requests(from_dt=start_dt, to_dt=end_dt, contribs_and_sessions=False)
        cal = icalendar.Calendar()
        cal.add('version', '2.0')
        cal.add('prodid', '-//CERN//INDICO//EN')
        now = now_utc()
        for req in results:
            data = _serialize_obj(req, alarm)
            _ical_serialize_vc(cal, data, now)
        return send_file('vc-assistance.ics', BytesIO(cal.to_ical()), 'text/calendar')


class RHRequestCalendarLink(RHVCSupportProtected):
    """Generate a signed calendar link"""

    def _process(self):
        form = RequestCalendarForm()
        if form.validate_on_submit():
            data = form.data
            url = signed_url_for_user(session.user, 'plugin_vc_assistance.request_calendar', _external=True, **data)
            session['vc_assistance_calendar_link_url'] = url
            return jsonify_data(flash=False)
        return jsonify_form(form, submit=_('Generate link'), disabled_until_change=False)
