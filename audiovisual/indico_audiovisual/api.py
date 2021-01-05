# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import re
from datetime import timedelta

import icalendar
from flask import request
from sqlalchemy.orm import noload

from indico.core import signals
from indico.core.db import db
from indico.modules.attachments.models.attachments import Attachment, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.contributions.models.subcontributions import SubContribution
from indico.modules.events.requests.models.requests import RequestState
from indico.modules.events.sessions.models.sessions import Session
from indico.web.flask.util import url_for
from indico.web.http_api import HTTPAPIHook
from indico.web.http_api.responses import HTTPAPIError
from indico.web.http_api.util import get_query_parameter

from indico_audiovisual import SERVICES, SHORT_SERVICES
from indico_audiovisual.definition import AVRequest
from indico_audiovisual.util import find_requests


def parse_indico_id(indico_id):
    event_match = re.match('(\d+)$', indico_id)
    session_match = re.match('(\d+)s(\d+)$', indico_id)
    contrib_match = re.match('(\d+)c(\d+)$', indico_id)
    subcontrib_match = re.match('(\d+)c(\d+)sc(\d+)$', indico_id)

    if subcontrib_match:
        event = Event.get(subcontrib_match.group(1), is_deleted=False)
        if not event:
            return None
        return SubContribution.find(SubContribution.id == subcontrib_match.group(3), ~SubContribution.is_deleted,
                                    SubContribution.contribution.has(event=event, id=subcontrib_match.group(2),
                                                                     is_deleted=False)).first()
    elif session_match:
        event = Event.get(session_match.group(1), is_deleted=False)
        return Session.query.with_parent(event).filter_by(id=session_match.group(2)).first()
    elif contrib_match:
        event = Event.get(contrib_match.group(1), is_deleted=False)
        return Contribution.query.with_parent(event).filter_by(id=contrib_match.group(2)).first()
    elif event_match:
        return Event.get(event_match.group(1), is_deleted=False)
    else:
        return None


def cds_link_exists(obj, url):
    query = (Attachment
             .find(~Attachment.is_deleted,
                   ~AttachmentFolder.is_deleted,
                   AttachmentFolder.object == obj,
                   Attachment.type == AttachmentType.link,
                   Attachment.link_url == url,
                   _join=AttachmentFolder)
             .options(noload('*')))
    return db.session.query(query.exists()).scalar()


def create_link(indico_id, cds_id, user):
    from indico_audiovisual.plugin import AVRequestsPlugin

    obj = parse_indico_id(indico_id)
    if obj is None:
        return False

    url = AVRequestsPlugin.settings.get('recording_cds_url')
    if not url:
        return False

    url = url.format(cds_id=cds_id)
    if cds_link_exists(obj, url):
        return True

    folder = AttachmentFolder.get_or_create_default(obj)
    attachment = Attachment(folder=folder, user=user, title='Recording', type=AttachmentType.link, link_url=url)
    db.session.add(attachment)
    db.session.flush()
    signals.attachments.attachment_created.send(attachment, user=user)
    return True


class RecordingLinkAPI(HTTPAPIHook):
    PREFIX = 'api'
    TYPES = ('create_cds_link',)
    RE = ''
    GUEST_ALLOWED = False
    VALID_FORMATS = ('json',)
    COMMIT = True
    HTTP_POST = True

    def _has_access(self, user):
        return AVRequest.can_be_managed(user)

    def _getParams(self):
        super(RecordingLinkAPI, self)._getParams()
        self._indico_id = get_query_parameter(self._queryParams, ['iid', 'indicoID'])
        self._cds_id = get_query_parameter(self._queryParams, ['cid', 'cdsID'])

    def api_create_cds_link(self, user):
        if not self._indico_id or not self._cds_id:
            raise HTTPAPIError('A required argument is missing.', 400)
        success = create_link(self._indico_id, self._cds_id, user)
        return {'success': success}


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

    def _has_access(self, user):
        return AVRequest.can_be_managed(user)

    @property
    def serializer_args(self):
        return {'ical_serializer': _ical_serialize_av}

    def export_webcast_recording(self, user):
        results = find_requests(talks=True, from_dt=self._fromDT, to_dt=self._toDT, services=self._services,
                                states=(RequestState.accepted, RequestState.pending))
        for req, contrib, _ in results:
            yield _serialize_obj(req, contrib, self._alarm)


def _get_room_name(obj, full=True):
    if obj.inherit_location and obj.location_parent is None:
        return ''
    room = obj.room
    if room is not None:
        name = room.full_name if full else (room.verbose_name or room.name)
    else:
        name = (obj.own_room_name if not obj.inherit_location else obj.location_parent.room_name)
    return name.replace('/', '-', 1)


def _serialize_obj(req, obj, alarm):
    # Util to serialize an event, contribution or subcontribution
    # in the context of a webcast/recording request
    url = title = unique_id = None
    date_source = location_source = obj
    if isinstance(obj, Event):
        url = obj.external_url
        title = obj.title
        unique_id = 'e{}'.format(obj.id)
    elif isinstance(obj, Contribution):
        url = url_for('contributions.display_contribution', obj, _external=True)
        title = '{} - {}'.format(obj.event.title, obj.title)
        unique_id = 'c{}'.format(obj.id)
    elif isinstance(obj, SubContribution):
        url = url_for('contributions.display_subcontribution', obj, _external=True)
        title = '{} - {} - {}'.format(obj.event.title, obj.contribution.title, obj.title)
        unique_id = 'sc{}'.format(obj.id)
        date_source = obj.contribution
        location_source = obj.contribution

    audience = None
    if 'webcast' in req.data['services']:
        audience = req.data['webcast_audience'] or 'No restriction'

    data = {
        'status': 'P' if req.state == RequestState.pending else 'A',
        'services': req.data['services'],
        'event_id': req.event_id,
        'startDate': date_source.start_dt,
        'endDate': date_source.end_dt,
        'title': title,
        'location': location_source.venue_name or None,
        'room': _get_room_name(location_source, full=False) or None,
        'room_full_name': _get_room_name(location_source, full=True) or None,
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
    location = ': '.join(filter(None, (record['location'], record['room_full_name'])))
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
