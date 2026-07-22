# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
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

from indico.modules.events.requests.models.requests import RequestState
from indico.util.date_time import as_utc, get_day_end, get_day_start, now_utc
from indico.util.iterables import group_list
from indico.util.marshmallow import RelativeDayDateTime
from indico.web.args import use_kwargs
from indico.web.flask.util import send_file
from indico.web.rh import RHProtected, allow_signed_url
from indico.web.util import jsonify_data, jsonify_form, signed_url_for_user

from indico_audiovisual import _
from indico_audiovisual.api import _ical_serialize_av, _serialize_obj
from indico_audiovisual.forms import RequestCalendarForm, RequestListFilterForm
from indico_audiovisual.util import find_requests, is_av_manager
from indico_audiovisual.views import WPAudiovisualManagers


class RHAVManagerProtected(RHProtected):
    def _check_access(self):
        RHProtected._check_access(self)
        if not is_av_manager(session.user):
            raise Forbidden


class RHRequestList(RHAVManagerProtected):
    """Provides a list of webcast/recording requests"""

    def _process(self):
        form = RequestListFilterForm(request.args, csrf_enabled=False)
        results = None
        if request.args and form.validate():
            reverse = form.direction.data == 'desc'
            talks = form.granularity.data == 'talks'
            from_dt = as_utc(get_day_start(form.start_date.data)) if form.start_date.data else None
            to_dt = as_utc(get_day_end(form.end_date.data)) if form.end_date.data else None
            states = {form.state.data} if form.state.data is not None else None
            has_comment = {'': None, 'no': False, 'yes': True}[form.has_comment.data or '']
            results = find_requests(talks=talks, from_dt=from_dt, to_dt=to_dt, states=states, has_comment=has_comment)
            if not talks:
                results = [(req, req.event, req.event.start_dt) for req in results]
            results = group_list(results, lambda x: x[2].date(), itemgetter(2), sort_reverse=reverse)
            results = dict(sorted(results.items(), key=itemgetter(0), reverse=reverse))

        calendar_link = session.pop('audiovisual_calendar_link_url', None)
        return WPAudiovisualManagers.render_template('request_list.html', form=form, results=results,
                                                     calendar_link_supported=True, calendar_link=calendar_link)


@allow_signed_url
class RHRequestCalendar(RHAVManagerProtected):
    """Provides a calendar of webcast/recording requests"""

    @use_kwargs({
        'alarm': fields.Int(load_default=0, validate=validate.Range(min=0)),
        'start_dt': RelativeDayDateTime(data_key='start_date', required=True),
        'end_dt': RelativeDayDateTime(data_key='end_date', day_end=True, required=True),
        'include': fields.List(fields.Str(), load_default=None),
    }, location='query')
    def _process(self, alarm, start_dt, end_dt, include):
        if include is not None:
            include = set(include)
        results = find_requests(talks=True, from_dt=start_dt, to_dt=end_dt, services=include,
                                states=(RequestState.accepted, RequestState.pending))
        cal = icalendar.Calendar()
        cal.add('version', '2.0')
        cal.add('prodid', '-//CERN//INDICO//EN')
        now = now_utc()
        for req, contrib, __ in results:
            data = _serialize_obj(req, contrib, alarm)
            _ical_serialize_av(cal, data, now)
        return send_file('audiovisual.ics', BytesIO(cal.to_ical()), 'text/calendar')


class RHRequestCalendarLink(RHAVManagerProtected):
    """Generate a signed calendar link"""

    def _process(self):
        form = RequestCalendarForm()
        if form.validate_on_submit():
            data = form.data
            url = signed_url_for_user(session.user, 'plugin_audiovisual.request_calendar', _external=True, **data)
            session['audiovisual_calendar_link_url'] = url
            return jsonify_data(flash=False)
        return jsonify_form(form, submit=_('Generate link'), disabled_until_change=False)
