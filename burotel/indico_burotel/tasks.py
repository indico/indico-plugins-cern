# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
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
    provider = multipass.identity_providers[cern_ident_provider]
    cern_ident = user.get_identity(cern_ident_provider)

    try:
        return cern_ident.multipass_data['cern_person_id']
    except (KeyError, TypeError, AttributeError):
        # no cern identity, no multipass data, or no person id in there
        pass

    # we have a cern identity, try refreshing its data
    # (for existing users we have no multipass data and thus no person id)
    if cern_ident:
        plugin.logger.info('Refreshing identity %r', cern_ident)
        info = provider.refresh_identity(cern_ident.identifier, cern_ident.multipass_data)
        cern_ident.data = info.data
        cern_ident.multipass_data = info.multipass_data
        try:
            return info.multipass_data['cern_person_id']
        except (TypeError, KeyError):
            plugin.logger.warning('Refreshed CERN identity without person id: %r', cern_ident)

    # try to fetch the identity from the source before giving up
    plugin.logger.info('Searching person id for %r in central database', user)
    results = multipass.search_identities(providers={cern_ident_provider}, exact=True, email=user.all_emails)
    for info in results:
        try:
            return info.multipass_data['cern_person_id']
        except (TypeError, KeyError):
            pass

    plugin.logger.error('Could not retrieve CERN Person ID for %r', user)
    return None


def _build_query(delta):
    attr = RoomAttribute.query.filter(RoomAttribute.name == 'confirmation-by-secretariat').one()
    return (
        Reservation.query
        .join(Room)
        .filter(
            Reservation.state == ReservationState.pending,
            # booking ends in the future
            Reservation.end_dt > now_utc(),
            # booking has started more than `delta` working days ago
            db.func.plugin_burotel.count_weekdays(db.cast(Reservation.start_dt, db.Date), now_utc().date()) > delta,
            Room.attributes.any(
                db.and_(
                    RoomAttributeAssociation.attribute == attr,
                    RoomAttributeAssociation.value == db.func.cast('yes', JSONB)
                )
            )
        )
    )


def _adams_request(action, user, room, start_dt, end_dt):
    from indico_burotel.plugin import BurotelPlugin

    username = BurotelPlugin.settings.get('adams_username')
    password = BurotelPlugin.settings.get('adams_password')
    logger = BurotelPlugin.logger

    person_id = _find_person_id(BurotelPlugin, user)

    if not person_id:
        logger.error("Task failed: can't find a Person ID for %s", user)
        return False

    url = BurotelPlugin.settings.get('adams_service_url').format(
        action=action,
        person_id=person_id,
        room=room.name.replace('-', '/'),
        start_dt=start_dt.isoformat(),
        end_dt=end_dt.isoformat()
    )

    try:
        res = requests.request('DELETE' if action == 'cancel' else 'POST', url, auth=(username, password), timeout=10)
        res.raise_for_status()
    except Timeout:
        logger.warning('Request timed out')
        raise Retry(message='Request timeout')
    except RequestException as e:
        logger.exception('Request failed (%d): %s', e.response.status_code, e.response.content)
        return False
    else:
        if res.status_code == 200:
            return True
        logger.error('Unexpected response status code:\nURL: %s\nCode: %s\nResponse: %s',
                     url, res.status_code, res.text)
        return False


# this task needs a request context since cancelling a booking will trigger an adams update
# to ensure the user does not have access (even though that has never been granted for a
# reservation which was still pending approval)
@celery.periodic_task(run_every=crontab(minute='0', hour='8'), plugin='burotel', request_context=True)
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
def update_access_permissions(booking, modify_dates=None):
    from indico_burotel.plugin import BurotelPlugin
    logger = BurotelPlugin.logger
    user = booking.booked_for_user

    if booking.state == ReservationState.accepted:
        if modify_dates:
            old_start_dt, old_end_dt = modify_dates
            logger.info(
                'Modifying access to %s: %s (%s - %s) -> (%s - %s)',
                booking.room,
                booking.booked_for_user,
                old_start_dt,
                old_end_dt,
                booking.start_dt,
                booking.end_dt
            )
            logger.info('Removing ADaMS access from %s: %s, %s - %s (booking rejected/cancelled)',
                        booking.room, booking.booked_for_user, old_start_dt, old_end_dt)
            suffix = ''
            if not _adams_request('cancel', booking.booked_for_user, booking.room, old_start_dt, old_end_dt):
                suffix = ' [FAILED]'
            date_range = f'{old_start_dt} - {old_end_dt}'
            booking.add_edit_log(ReservationEditLog(user_name='Burotel', info=[
                f'Removing current access from {user.full_name} ({user.id}), {date_range} (booking created){suffix}'
            ]))

        logger.info('Granting ADaMS access to %s: %s, %s - %s',
                    booking.room, booking.booked_for_user, booking.start_dt, booking.end_dt)
        suffix = ''
        if not _adams_request('create', booking.booked_for_user, booking.room, booking.start_dt.date(),
                              booking.end_dt.date()):
            suffix = ' [FAILED]'
        date_range = f'{booking.start_dt.date()} - {booking.end_dt.date()}'
        booking.add_edit_log(ReservationEditLog(user_name='Burotel', info=[
            f'Granting ADaMS access to {user.full_name} ({user.id}), {date_range} (booking created){suffix}'
        ]))
    elif booking.state in {ReservationState.cancelled, ReservationState.rejected}:
        logger.info('Removing ADaMS access from %s: %s, %s - %s (booking rejected/cancelled)',
                    booking.room, booking.booked_for_user, booking.start_dt, booking.end_dt)
        suffix = ''
        if not _adams_request('cancel', booking.booked_for_user, booking.room, booking.start_dt.date(),
                              booking.end_dt.date()):
            suffix = ' [FAILED]'
        date_range = f'{booking.start_dt.date()} - {booking.end_dt.date()}'
        booking.add_edit_log(ReservationEditLog(user_name='Burotel', info=[
            f'Removing ADaMS access from {user.full_name} ({user.id}), {date_range} '
            f'(booking rejected/cancelled){suffix}'
        ]))
    else:
        return

    db.session.commit()
    logger.debug('Done')
