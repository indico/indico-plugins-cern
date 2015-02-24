from __future__ import unicode_literals
from datetime import timedelta

import icalendar
from flask import request

from indico.core.db import db
from indico.core.db.sqlalchemy.util.queries import limit_groups
from indico.modules.events.requests.models.requests import Request, RequestState
from indico.modules.fulltextindexes.models.events import IndexedEvent
from indico.util.string import to_unicode
from indico.web.flask.util import url_for
from indico.web.http_api import HTTPAPIHook
from indico.web.http_api.util import get_query_parameter
from MaKaC.conference import Conference, Contribution, SubContribution

from indico_audiovisual import SERVICES, SHORT_SERVICES
from indico_audiovisual.definition import AVRequest
from indico_audiovisual.util import get_selected_contributions


class AVExportHook(HTTPAPIHook):
    TYPES = (AVRequest.name,)
    RE = ''
    DEFAULT_DETAIL = 'default'
    MAX_RECORDS = {'default': 100}
    GUEST_ALLOWED = False
    VALID_FORMATS = ('json', 'jsonp', 'xml', 'ics')

    def _getParams(self):
        super(AVExportHook, self)._getParams()
        self._services = set(request.args.getlist('service'))
        self._alarm = get_query_parameter(self._queryParams, ['alarms'], None, True)

    def _hasAccess(self, aw):
        return AVRequest.can_be_managed(aw.getUser())

    @property
    def serializer_args(self):
        return {'ical_serializer': _ical_serialize_av}

    def export_webcast_recording(self, aw):
        query = Request.find(Request.type == AVRequest.name,
                             Request.state.in_((RequestState.accepted, RequestState.pending)))
        if self._fromDT:
            query = query.join(IndexedEvent, IndexedEvent.id == db.cast(Request.event_id, db.String))
            if self._fromDT:
                query = query.filter(IndexedEvent.start_date >= self._fromDT)
        # We only want the latest one for each event
        query = limit_groups(query, Request, Request.event_id, Request.created_dt.desc(), 1)
        for req in query:
            event = req.event

            # Skip requests which do not have the requested services or are outside the date range
            if self._services and not (set(req.data['services']) & self._services):
                continue
            elif self._toDT and event.getStartDate() > self._toDT:
                continue

            # Lectures don't have contributions so we use the event info directly
            if event.getType() == 'simple_event':
                yield _serialize_obj(req, event, self._alarm)
                continue

            contribs = [contrib for contrib, capable, _ in get_selected_contributions(req) if capable]
            for contrib in contribs:
                if self._fromDT and _get_start_date(contrib) < self._fromDT:
                    continue
                elif self._toDT and _get_start_date(contrib) > self._toDT:
                    continue
                yield _serialize_obj(req, contrib, self._alarm)


def _get_start_date(obj):
    if isinstance(obj, SubContribution):
        return obj.getContribution().getStartDate()
    else:
        return obj.getStartDate()


def _serialize_obj(req, obj, alarm):
    # Util to serialize an event, contribution or subcontribution
    # in the context of a webcast/recording request
    url = title = unique_id = None
    date_source = obj
    if isinstance(obj, Conference):
        url = url_for('event.conferenceDisplay', obj, _external=True)
        title = to_unicode(obj.getTitle())
        unique_id = 'e{}'.format(obj.id)
    elif isinstance(obj, Contribution):
        url = url_for('event.contributionDisplay', obj, _external=True)
        title = '{} - {}'.format(to_unicode(obj.getConference().getTitle()),
                                 to_unicode(obj.getTitle()))
        unique_id = 'e{}c{}'.format(obj.getConference().id, obj.id)
    elif isinstance(obj, SubContribution):
        url = url_for('event.subContributionDisplay', obj, _external=True)
        title = '{} - {} - {}'.format(to_unicode(obj.getConference().getTitle()),
                                      to_unicode(obj.getContribution().getTitle()),
                                      to_unicode(obj.getTitle()))
        unique_id = 'e{}c{}-{}'.format(obj.getConference().id, obj.getContribution().id, obj.id)
        date_source = obj.getContribution()

    audience = None
    if 'webcast' in req.data['services']:
        audience = req.data['webcast_audience'] or 'No restriction'

    data = {
        'status': 'P' if req.state == RequestState.pending else 'A',
        'services': req.data['services'],
        'event_id': req.event_id,
        'startDate': date_source.getStartDate(),
        'endDate': date_source.getEndDate(),
        'title': title,
        'location': to_unicode(obj.getLocation().getName() if obj.getLocation() else None),
        'room': to_unicode(obj.getRoom().getName() if obj.getRoom() else None),
        'url': url,
        'audience': audience,
        '_ical_id': 'indico-audiovisual-{}@cern.ch'.format(unique_id)
    }
    if alarm:
        data['_ical_alarm'] = alarm
    return data


def _ical_summary(record):
    return '{}:{} - {}'.format('+'.join(map(SHORT_SERVICES.get, record['services'])),
                               record['status'],
                               record['title'])


def _ical_serialize_av(cal, record, now):
    event = icalendar.Event()
    event.add('uid', record['_ical_id'])
    event.add('dtstamp', now)
    event.add('dtstart', record['startDate'])
    event.add('dtend', record['endDate'])
    event.add('url', record['url'])
    event.add('categories', 'Webcast/Recording')
    event.add('summary', _ical_summary(record))
    location = ': '.join(filter(None, (record['location'], record['room'])))
    event.add('location', location)
    description = ['URL: {}'.format(record['url']),
                   'Services: {}'.format(', '.join(map(unicode, map(SERVICES.get, record['services']))))]
    if record['audience']:
        description.append('Audience: {}'.format(record['audience']))
    event.add('description', '\n'.join(description))
    if '_ical_alarm' in record:
        event.add_component(_ical_serialize_av_alarm(record))
    cal.add_component(event)


def _ical_serialize_av_alarm(record):
    alarm = icalendar.Alarm()
    alarm.add('trigger', timedelta(minutes=-int(record['_ical_alarm'])))
    alarm.add('action', 'DISPLAY')
    alarm.add('summary', _ical_summary(record))
    alarm.add('description', str(record['url']))
    return alarm
