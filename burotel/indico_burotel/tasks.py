# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import requests
from celery.exceptions import Retry
from celery.schedules import crontab
from flask_pluginengine import current_plugin
from requests.exceptions import RequestException, Timeout
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Interval

from indico.core.auth import multipass
from indico.core.celery import celery
from indico.core.db import db
from indico.modules.rb.models.reservations import Reservation, ReservationEditLog, ReservationState
from indico.modules.rb.models.room_attributes import RoomAttribute, RoomAttributeAssociation
from indico.modules.rb.models.rooms import Room
from indico.modules.users.models.users import User
from indico.util.date_time import now_utc

from indico_burotel.notifications import notify_about_to_cancel, notify_automatic_cancellation


def _find_person_id(plugin, user):
    """Get the CERN Person ID of a user."""
    cern_ident_provider = plugin.settings.get('cern_identity_provider')
    cern_ident_provider = plugin.settings.get('cern_identity_provider')
    cern_ident = user.get_identity(cern_ident_provider)

    if not cern_ident:
        # try to fetch the identity from the source before giving up
        results = multipass.search_identities(providers={cern_ident_provider}, exact=True, email=user.all_emails)
        if not (cern_ident := next(results, None)):
            # that didn't work out, raise an error
            raise Exception(f"Can't find '{cern_ident_provider}' identity for {user}")

    if not (person_id := cern_ident.multipass_data.get('cern_person_id')):
        raise Exception(f"Can't find CERN Person ID in '{cern_ident_provider}' identity for {user}")

    return person_id


def _build_query(delta):
    attr = RoomAttribute.query.filter(RoomAttribute.name == 'confirmation-by-secretariat').one()
    reservation = db.aliased(Reservation)

    # get all days between two dates
    subq = db.session.query(db.func.generate_series(
        reservation.start_dt,
        now_utc(),
        db.func.cast('1 day', Interval)
    ).label('d')).subquery()

    # count all days except for weekends (working days)
    query = db.session.query(
        db.func.count(subq.c.d).label('d')
    ).filter(db.func.extract('dow', subq.c.d).notin_({0, 6})).subquery()

    return reservation.query.filter(
        reservation.state == ReservationState.pending,
        # booking ends in the future
        reservation.end_dt > now_utc(),
        # booking has started more than `delta` working days ago
        query.c.d > delta,
        Room.attributes.any(
            db.and_(
                RoomAttributeAssociation.attribute == attr,
                RoomAttributeAssociation.value == db.func.cast('yes', JSONB)
            )
        )
    ).join(Room)


def _adams_request(action, user, room, start_dt, end_dt):
    from indico_burotel.plugin import BurotelPlugin

    username = BurotelPlugin.settings.get('adams_username')
    password = BurotelPlugin.settings.get('adams_password')
    logger = BurotelPlugin.logger

    person_id = _find_person_id(BurotelPlugin, user)

    if not person_id:
        logger.error("Task failed: can't find a Person ID for %s", user)
        return

    url = BurotelPlugin.settings.get('adams_service_url').format(
        action=action,
        person_id=person_id,
        room=room.name.replace('-', '/'),
        start_dt=start_dt.date().isoformat(),
        end_dt=end_dt.date().isoformat()
    )

    try:
        res = requests.request('DELETE' if action == 'cancel' else 'POST', url, auth=(username, password), timeout=10)
        res.raise_for_status()
    except Timeout:
        logger.warning('Request timed out')
        raise Retry(message='Request timeout')
    except RequestException as e:
        logger.exception('Request failed (%d): %s', e.response.status_code, e.response.content)
    else:
        if res.status_code == 200:
            return
        logger.error('Unexpected response status code:\nURL: %s\nCode: %s\nResponse: %s',
                     url, res.status_code, res.text)


@celery.periodic_task(run_every=crontab(minute='0', hour='8'), plugin='burotel')
def auto_cancel_bookings():
    # bookings which should be cancelled
    for booking in _build_query(3):
        current_plugin.logger.info('Auto-cancelling booking %s', booking)
        booking.cancel(User.get_system_user(), silent=True)
        booking.add_edit_log(ReservationEditLog(
            user_name=User.get_system_user().full_name,
            info=['Cancelled automatically due to lack of confirmation']
        ))
        notify_automatic_cancellation(booking)

    db.session.flush()

    # bookings which are about to be cancelled
    for email in _build_query(2):
        notify_about_to_cancel(email)
    db.session.commit()


@celery.task
def update_access_permissions(booking):
    from indico_burotel.plugin import BurotelPlugin
    logger = BurotelPlugin.logger
    user = booking.booked_for_user

    if booking.state == ReservationState.accepted:
        logger.info('Granting ADaMS access to %s: %s, %s - %s',
                    booking.room, booking.booked_for_user, booking.start_dt, booking.end_dt)
        _adams_request('create', booking.booked_for_user, booking.room, booking.start_dt,
                       booking.end_dt)
        booking.add_edit_log(ReservationEditLog(user_name="Burotel", info=[
            'Granting ADaMS access to {} ({}), {} - {} (booking created)'.format(
                user.full_name, user.id, booking.start_dt.date(), booking.end_dt.date()
            )
        ]))
    elif booking.state in {ReservationState.cancelled, ReservationState.rejected}:
        logger.info('Removing ADaMS access from %s: %s, %s - %s (booking rejected/cancelled)',
                    booking.room, booking.booked_for_user, booking.start_dt, booking.end_dt)
        booking.add_edit_log(ReservationEditLog(user_name="Burotel", info=[
            'Removing ADaMS access from {} ({}), {} - {} (booking rejected/cancelled)'.format(
                user.full_name, user.id, booking.start_dt.date(), booking.end_dt.date()
            )
        ]))
        _adams_request('cancel', booking.booked_for_user, booking.room, booking.start_dt,
                       booking.end_dt)
    else:
        return

    db.session.commit()
    logger.debug('Done')
