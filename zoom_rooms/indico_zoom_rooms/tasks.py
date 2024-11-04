# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from pprint import pformat

import requests
from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db
from indico.util.string import strip_control_chars

from indico_zoom_rooms.models import ZoomRoomsAction, ZoomRoomsQueueEntry


def _send_request(method: str, zr_id: str, entry_id: str, data: dict | None = None) -> bool:
    """Send a request to the corresponding HTTP service."""
    from indico_zoom_rooms.plugin import ZoomRoomsPlugin
    logger = ZoomRoomsPlugin.logger

    path = f'/api/v1/users/{zr_id}/events/{entry_id}'
    if not (url := ZoomRoomsPlugin.settings.get('service_url')):
        raise RuntimeError('service_url is not set!')
    url = url.rstrip('/') + path

    if not (token := ZoomRoomsPlugin.settings.get('token')):
        raise RuntimeError('token is not set!')
    try:
        res = requests.request(
            method,
            url,
            json=data,
            headers={'Authorization': f'Bearer {token}'},
            timeout=ZoomRoomsPlugin.settings.get('timeout'),
        )
        logger.info('%s request to %s finished with status %r and body %r', method, path, res.status_code, res.text)
        res.raise_for_status()
        return True
    except requests.Timeout:
        logger.warning('Request timed out')
    except requests.RequestException:
        logger.exception('%s request failed:\nURL: %s\nData: %s', method, url, pformat(data))
    except requests.HTTPError:
        logger.error(
            'Request unsuccessful:\nURL: %s\nData: %s\nCode: %s\nResponse: %s',
            url,
            pformat(data),
            res.status_code,
            res.text,
        )

    return False


def put_entry(zr_id: str, entry_id: str, entry: dict) -> bool:
    """Trigger a PUT request (creation and update)."""
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
    """Trigger a DELETE request."""
    return _send_request('DELETE', zr_id, entry_id)


@celery.periodic_task(run_every=crontab(minute='*'), plugin='vc_zoom')
def update_zoom_rooms_calendar_entries():
    """Periodic task which sends all queued up entries and sends them to the HTTP API."""
    to_delete = set()
    from indico_zoom_rooms.plugin import ZoomRoomsPlugin
    logger = ZoomRoomsPlugin.logger

    for entry in ZoomRoomsQueueEntry.query.order_by(ZoomRoomsQueueEntry.id).all():
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
