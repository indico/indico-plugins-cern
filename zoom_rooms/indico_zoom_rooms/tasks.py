# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from pprint import pformat

import requests
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from sqlalchemy.orm.attributes import flag_modified

from indico.core.celery import celery
from indico.core.db import db
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.models.events import Event
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.util.string import strip_control_chars

from indico_zoom_rooms.models import ZoomRoomsAction, ZoomRoomsQueueEntry


def obj_from_locator(locator: dict) -> Contribution | SessionBlock | Event:
    if 'contrib_id' in locator:
        return Contribution.get(locator['contrib_id'])
    elif 'block_id' in locator:
        return SessionBlock.get(locator['block_id'])
    elif 'event_id' in locator:
        return Event.get(locator['event_id'])
    else:
        raise ValueError("Can't decode locator")


def update_state_log(log_entry, failed):
    log_entry.data['State'] = 'failed' if failed else 'succeeded'
    flag_modified(log_entry, 'data')


logger = get_task_logger(__name__)


def _send_request(method: str, zr_id: str, entry_id: str, data: dict | None = None) -> bool:
    from indico_zoom_rooms.plugin import ZoomRoomsPlugin

    path = f'/api/v1/users/{zr_id}/events/{entry_id}'
    if not (url := ZoomRoomsPlugin.settings.get('service_url')):
        raise KeyError('service_url is not set!')
    url = url.rstrip('/') + path

    if not (token := ZoomRoomsPlugin.settings.get('token')):
        raise KeyError('token is not set!')
    try:
        res = requests.request(
            method,
            url,
            json=data,
            headers={'Authorization': f'Bearer {token}'},
            timeout=ZoomRoomsPlugin.settings.get('timeout'),
        )
    except requests.Timeout:
        logger.warning('Request timed out')
    except requests.RequestException:
        logger.exception('%s request failed:\nURL: %s\nData: %s', method, url, pformat(data))
    else:
        logger.info('%s request to %s finished with status %r and body %r', method, path, res.status_code, res.text)
        if res.ok:
            return True
        logger.error(
            'Request unsuccessful:\nURL: %s\nData: %s\nCode: %s\nResponse: %s',
            url,
            pformat(data),
            res.status_code,
            res.text,
        )

    return False


def put_entry(zr_id: str, entry_id: str, entry: dict) -> bool:
    return _send_request(
        'PUT',
        zr_id,
        entry_id,
        {
            'status': 'BUSY',
            'start': entry['start_dt'],
            'end': entry['end_dt'],
            'subject': strip_control_chars(entry['title']),
            'body': f'<a href="{entry['url']}">{entry['url']}</a>',
        },
    )


def delete_entry(zr_id: str, entry_id: str) -> bool:
    return _send_request('DELETE', zr_id, entry_id)


@celery.periodic_task(run_every=crontab(minute='*/1'), plugin='vc_zoom')
def update_zoom_rooms_calendar_entries():
    to_delete = set()
    for entry in ZoomRoomsQueueEntry.query.all():
        match entry.action:
            case ZoomRoomsAction.create:
                logger.info('Creating entry %s for user %s: %s', entry.entry_id, entry.zoom_room_id, entry.entry_data)
                put_entry(entry.zoom_room_id, entry.entry_id, entry.entry_data)
            case ZoomRoomsAction.delete:
                logger.info('Deleting entry %s for user %s', entry.entry_id, entry.zoom_room_id)
                delete_entry(entry.zoom_room_id, entry.entry_id)
            case ZoomRoomsAction.update:
                logger.info('Updating entry %s for user %s: %s', entry.entry_id, entry.zoom_room_id, entry.entry_data)
                put_entry(entry.zoom_room_id, entry.entry_id, entry.entry_data)
            case ZoomRoomsAction.move:
                logger.info(
                    'Moving entry %s for user %s (-> %s): %s',
                    entry.entry_id,
                    entry.zoom_room_id,
                    entry.extra_args['new_zr_id'],
                    entry.entry_data,
                )
                delete_entry(entry.zoom_room_id, entry.entry_id)
                put_entry(entry.extra_args['new_zr_id'], entry.entry_id, entry.entry_data)
            case action:
                raise ValueError(f'unrecognized action {action}')
        to_delete.add(entry)

    if to_delete:
        for entry in to_delete:
            db.session.delete(entry)
        db.session.commit()
