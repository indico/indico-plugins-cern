# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date, datetime

import pytest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.rb.models.reservations import Reservation
from indico.modules.rb.models.room_attributes import RoomAttribute
from indico.modules.rb.models.rooms import RoomAttributeAssociation
from indico.web.flask.util import url_for

from indico_burotel.tasks import auto_cancel_bookings


pytest_plugins = 'indico.modules.rb.testing.fixtures'
pytestmark = [pytest.mark.usefixtures('smtp')]


class NoCSRFTestClient:
    def __init__(self, client):
        self.client = client

    def __getattr__(self, attr):
        def _verb_wrapper(*args, **kwargs):
            headers = kwargs.get('headers', {})
            headers['X-CSRF-Token'] = 'dummy'
            kwargs['headers'] = headers
            return getattr(self.client, attr)(*args, **kwargs)

        if attr in {'post', 'patch', 'delete'}:
            return _verb_wrapper
        else:
            return getattr(self.client, attr)


@pytest.fixture(autouse=True)
def room_attributes(db):
    attr_approval = RoomAttribute(name='confirmation-by-secretariat', title="Secretariat must confirm")
    attr_lock = RoomAttribute(name='electronic-lock', title="Electronic Lock")
    db.session.add(attr_approval)
    db.session.add(attr_lock)
    db.session.flush()
    return (attr_lock, attr_approval)


@pytest.fixture(autouse=True)
def back_to_the_past(freeze_time):
    freeze_time(datetime(2020, 1, 1))


@pytest.fixture
def no_csrf_client(test_client, monkeypatch):
    monkeypatch.setattr('indico.web.flask.session.IndicoSession.csrf_token', property(lambda self: 'dummy'))
    return NoCSRFTestClient(test_client)


def test_update_called_on_create(db, dummy_user, mocker, create_room, no_csrf_client, room_attributes):
    attr_lock = room_attributes[0]

    adams_request = mocker.patch('indico_burotel.tasks._adams_request')
    room = create_room()

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    assert no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-02-01",
        'end_dt': "2020-02-02",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id
    }).status_code == 200

    assert not adams_request.called

    # ADaMS is only contacted for rooms with 'electronic-lock' set to 'yes'
    room.attributes.append(RoomAttributeAssociation(attribute=attr_lock, value='yes'))
    db.session.flush()

    assert no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-02-03",
        'end_dt': "2020-02-04",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id
    }).status_code == 200

    adams_request.assert_called_once_with('create', dummy_user, room, date(2020, 2, 3), date(2020, 2, 4))


def test_update_called_on_accept(create_room, mocker, no_csrf_client, dummy_user, room_attributes):
    attr_lock = room_attributes[0]

    adams_request = mocker.patch('indico_burotel.tasks._adams_request')
    room = create_room(protection_mode=ProtectionMode.public, reservations_need_confirmation=True)

    room.attributes.append(RoomAttributeAssociation(attribute=attr_lock, value='yes'))

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-02-01",
        'end_dt': "2020-02-02",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
        'is_prebooking': True
    })
    assert response.status_code == 200
    prebooking = Reservation.get(response.json['booking']['id'])

    assert not adams_request.called

    no_csrf_client.post(url_for('rb.booking_state_actions', booking_id=prebooking.id, action='approve'))

    # after the pre-booking is accepted, _adams_request should be called
    adams_request.assert_called_once_with('create', dummy_user, room, date(2020, 2, 1), date(2020, 2, 2))


def test_update_called_on_modify(create_room, mocker, no_csrf_client, dummy_user, room_attributes):
    attr_lock = room_attributes[0]

    adams_request = mocker.patch('indico_burotel.tasks._adams_request')
    room = create_room(protection_mode=ProtectionMode.public, reservations_need_confirmation=True)

    room.attributes.append(RoomAttributeAssociation(attribute=attr_lock, value='yes'))

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': '2020-02-01',
        'end_dt': '2020-02-02',
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id
    })

    assert response.status_code == 200

    adams_request.assert_called_once_with('create', dummy_user, room, date(2020, 2, 1), date(2020, 2, 2))

    adams_request.reset_mock()

    response = no_csrf_client.patch(url_for('rb.update_booking', booking_id=response.json['booking']['id']), data={
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
        'start_dt': '2020-02-02',
        'end_dt': '2020-02-03'
    })

    assert response.status_code == 200

    assert adams_request.call_args_list == [
        (('cancel', dummy_user, room, date(2020, 2, 1), date(2020, 2, 2)),),
        (('create', dummy_user, room, date(2020, 2, 2), date(2020, 2, 3)),)
    ]


def test_update_called_on_reject(dummy_user, create_room, mocker, no_csrf_client, room_attributes):
    attr_lock = room_attributes[0]

    adams_request = mocker.patch('indico_burotel.tasks._adams_request')
    room = create_room(attributes=[RoomAttributeAssociation(attribute=attr_lock, value='yes')])

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-02-05",
        'end_dt': "2020-02-06",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
    })
    assert response.status_code == 200
    booking = Reservation.get(response.json['booking']['id'])

    adams_request.assert_called_once_with('create', dummy_user, room, date(2020, 2, 5), date(2020, 2, 6))

    no_csrf_client.post(url_for('rb.booking_state_actions', booking_id=booking.id, action='cancel'))

    # after the pre-booking is accepted, _adams_request should be called
    adams_request.assert_called_with('cancel', dummy_user, room, date(2020, 2, 5), date(2020, 2, 6))

    assert adams_request.call_count == 2


def test_auto_cancel(db, create_room, mocker, no_csrf_client, dummy_user, room_attributes, freeze_time):
    attr_approval = room_attributes[1]

    notify_cancel = mocker.patch('indico_burotel.tasks.notify_automatic_cancellation')
    notify_about_to_cancel = mocker.patch('indico_burotel.tasks.notify_about_to_cancel')

    room = create_room(protection_mode=ProtectionMode.public, reservations_need_confirmation=True,
                       attributes=[RoomAttributeAssociation(attribute=attr_approval, value='yes')])

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-03-02",  # This is a Monday
        'end_dt': "2020-03-10",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
        'is_prebooking': True
    })
    assert response.status_code == 200

    # 1 day after the start date, no warning, no cancellation
    freeze_time(datetime(2020, 3, 3))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 2 days after the start date, a warning
    freeze_time(datetime(2020, 3, 4))
    auto_cancel_bookings()
    assert notify_about_to_cancel.called
    assert not notify_cancel.called

    # reset mocks
    notify_about_to_cancel.reset_mock()
    notify_cancel.reset_mock()

    # 3 days after the start date, cancellation happens
    freeze_time(datetime(2020, 3, 5))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert notify_cancel.called


def test_auto_cancel_weekend(db, create_room, mocker, no_csrf_client, dummy_user, room_attributes, freeze_time):
    attr_approval = room_attributes[1]

    notify_cancel = mocker.patch('indico_burotel.tasks.notify_automatic_cancellation')
    notify_about_to_cancel = mocker.patch('indico_burotel.tasks.notify_about_to_cancel')

    room = create_room(protection_mode=ProtectionMode.public, reservations_need_confirmation=True,
                       attributes=[RoomAttributeAssociation(attribute=attr_approval, value='yes')])

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-03-05",  # This is a Thursday
        'end_dt': "2020-03-15",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
        'is_prebooking': True
    })
    assert response.status_code == 200

    # 1 day after the start date, no warning, no cancellation
    freeze_time(datetime(2020, 3, 6))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 2 days after the start date, still nothing (weekend)
    freeze_time(datetime(2020, 3, 7))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 3 days after the start date, same
    freeze_time(datetime(2020, 3, 8))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 4 days after the start date, cancellation warning
    freeze_time(datetime(2020, 3, 9))
    auto_cancel_bookings()
    assert notify_about_to_cancel.called
    assert not notify_cancel.called

    # reset mocks
    notify_about_to_cancel.reset_mock()
    notify_cancel.reset_mock()

    # 5 days after the start date, cancellation happens
    freeze_time(datetime(2020, 3, 10))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert notify_cancel.called


def test_no_auto_cancel(db, create_room, mocker, no_csrf_client, dummy_user, room_attributes, freeze_time):
    notify_cancel = mocker.patch('indico_burotel.tasks.notify_automatic_cancellation')
    notify_about_to_cancel = mocker.patch('indico_burotel.tasks.notify_about_to_cancel')

    # room id not set for automatic cancellation
    room = create_room(protection_mode=ProtectionMode.public, reservations_need_confirmation=True)

    with no_csrf_client.session_transaction() as sess:
        sess.set_session_user(dummy_user)

    response = no_csrf_client.post(url_for('rb.create_booking'), data={
        'start_dt': "2020-03-02",  # This is a Monday
        'end_dt': "2020-03-10",
        'repeat_frequency': 'DAY',
        'repeat_interval': 1,
        'booked_for_user': dummy_user.identifier,
        'booking_reason': 'just chillin',
        'room_id': room.id,
        'is_prebooking': True
    })
    assert response.status_code == 200

    # 1 day after the start date, no warning, no cancellation
    freeze_time(datetime(2020, 3, 3))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 2 days after the start date, no warning, no cancellation
    freeze_time(datetime(2020, 3, 4))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called

    # 3 days after the start date, no warning, no cancellation
    freeze_time(datetime(2020, 3, 5))
    auto_cancel_bookings()
    assert not notify_about_to_cancel.called
    assert not notify_cancel.called
