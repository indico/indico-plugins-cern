# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.sql import text

from indico.modules.categories.models.categories import Category
from indico.modules.events.contributions.operations import create_contribution, delete_contribution, update_contribution
from indico.modules.events.models.events import Event
from indico.modules.events.operations import clone_event, update_event
from indico.modules.events.sessions.operations import create_session, delete_session, update_session_block
from indico.modules.events.timetable.operations import (create_session_block_entry, move_timetable_entry,
                                                        schedule_contribution, update_timetable_entry)
from indico.modules.events.util import track_time_changes
from indico.modules.rb.models.room_attributes import RoomAttribute, RoomAttributeAssociation

from indico_zoom_rooms.models import ZoomRoomsAction, ZoomRoomsQueueEntry


TZ = ZoneInfo('Europe/Zurich')


def _entry_data(entry: ZoomRoomsQueueEntry) -> dict:
    return {
        'type': entry.action,
        'entry_id': entry.entry_id,
        'entry_data': entry.entry_data,
        'zoom_room_id': entry.zoom_room_id,
        'extra_args': entry.extra_args,
    }


@pytest.fixture
def db_reset_seqs(db):
    for type_ in (Event, db.m.Contribution, db.m.SessionBlock, db.m.Room):
        table = type_.__table__
        db.engine.execute(text(f'ALTER SEQUENCE {table.schema}.{table.name}_id_seq RESTART WITH 1'))
    return db


@pytest.fixture
def zr_room_attribute():
    return RoomAttribute(name='zoom-rooms-calendar-id', title='Exchange User Id')


@pytest.fixture
def create_zr_powered_room(create_room, db_reset_seqs, zr_room_attribute):
    from indico.core.db import db

    def _create(name, id):
        room = create_room(building=666, verbose_name=name)
        room.attributes.append(RoomAttributeAssociation(room=room, attribute=zr_room_attribute, value=id))
        db.session.flush()
        return room

    return _create


@pytest.fixture
def mock_tasks(db_reset_seqs):
    _data = {'last_id': 0}

    def _reset():
        last_entry = ZoomRoomsQueueEntry.query.order_by(db_reset_seqs.desc(ZoomRoomsQueueEntry.id)).first()
        _data['last_id'] = last_entry.id

    def _get_entries():
        for entry in (
            ZoomRoomsQueueEntry.query.filter(ZoomRoomsQueueEntry.id > _data['last_id'])
            .order_by(ZoomRoomsQueueEntry.id)
            .all()
        ):
            yield entry
            _data['last_id'] = entry.id

    _get_entries.reset = _reset

    return _get_entries


@pytest.fixture
def zr_powered_room(create_zr_powered_room):
    return create_zr_powered_room('ZoomRooms-powered Room', 'test-zoom-room-1@example.com')


@pytest.fixture
def another_zr_powered_room(create_zr_powered_room):
    return create_zr_powered_room('ZoomRooms-powered Room #2', 'test-zoom-room-2@example.com')


@pytest.fixture
def zr_event(create_zoom_meeting, create_event, zoom_api, db_reset_seqs, zr_powered_room, mock_tasks):
    event = create_event(
        creator=zoom_api['user'],
        creator_has_privileges=True,
        start_dt=datetime(2024, 3, 1, 16, 0, tzinfo=TZ),
        end_dt=datetime(2024, 3, 1, 18, 0, tzinfo=TZ),
        title='Test Event #1',
        room=zr_powered_room,
    )

    create_zoom_meeting(event, 'event').events[0]

    return event


@pytest.fixture
def zr_contrib(
    zr_event,
    create_contribution,
    create_timetable_entry,
    create_zoom_meeting,
    zr_powered_room,
    another_zr_powered_room,
    mock_tasks,
):
    contrib = create_contribution(title='Test Contribution #1', event=zr_event)

    # schedule contribution at 16:15
    create_timetable_entry(zr_event, contrib, start_dt=datetime(2024, 3, 1, 16, 15, 0, tzinfo=TZ))
    # create a zoom meeting for the contribution
    create_zoom_meeting(
        contrib,
        'contribution',
    ).events[0]

    return contrib


@pytest.fixture
def zr_session(zr_event, zr_powered_room, app_context, dummy_room, create_zoom_meeting, mock_tasks):
    with app_context.test_request_context():
        session = create_session(zr_event, {'title': 'Test Session #1'})

        block_entry_1 = create_session_block_entry(
            session, {'duration': timedelta(minutes=30), 'start_dt': datetime(2024, 3, 1, 16, 15, 0, tzinfo=TZ)}
        )
        block_entry_2 = create_session_block_entry(
            session,
            {
                'duration': timedelta(minutes=30),
                'location_data': {'room': dummy_room, 'venue': dummy_room.location, 'inheriting': False},
                'start_dt': datetime(2024, 3, 1, 17, 15, 0, tzinfo=TZ),
            },
        )

    block_1 = block_entry_1.session_block
    block_2 = block_entry_2.session_block

    contrib_1 = create_contribution(
        zr_event, {'title': 'Test Contribution #1', 'duration': timedelta(minutes=20)}, session_block=block_1
    )
    contrib_2 = create_contribution(
        zr_event, {'title': 'Test Contribution #2', 'duration': timedelta(minutes=20)}, session_block=block_2
    )

    # schedule contribution 1 at 16:15
    schedule_contribution(contrib_1, datetime(2024, 3, 1, 16, 15, 0, tzinfo=TZ), session_block=block_1)
    # schedule contribution 2 at 17:15
    schedule_contribution(contrib_2, datetime(2024, 3, 1, 17, 15, 0, tzinfo=TZ), session_block=block_2)

    # create a zoom meeting for contribution 1
    create_zoom_meeting(
        contrib_1,
        'contribution',
    ).events[0]

    # create a zoom meeting for contribution 2
    create_zoom_meeting(
        contrib_2,
        'contribution',
    ).events[0]

    # create a zoom meeting for session block 1
    create_zoom_meeting(
        block_1,
        'block',
    ).events[0]
    # create a zoom meeting for session block 2
    create_zoom_meeting(
        block_2,
        'block',
    ).events[0]

    return (
        session,
        block_1,
        block_2,
        contrib_1,
        contrib_2,
    )


EVENT_ENTRY_ID = 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting1'
ENTRY_TITLE = 'Zoom Meeting'


def test_event(zr_event, mock_tasks, dummy_room, zr_powered_room):
    tasks = mock_tasks()

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 0, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 0, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    with track_time_changes():
        # change time of event
        update_event(
            zr_event,
            start_dt=datetime(2024, 3, 1, 17, 0, tzinfo=TZ),
            end_dt=datetime(2024, 3, 1, 19, 0, tzinfo=TZ),
        )

    tasks = mock_tasks()

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.update,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 0, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 19, 0, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # event changes room (to non-enabled)
    update_event(
        zr_event,
        location_data={'room': dummy_room, 'venue': dummy_room.location, 'inheriting': False},
    )

    tasks = mock_tasks()

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # event changes room (to ZR-enabled)
    update_event(
        zr_event,
        location_data={'room': zr_powered_room, 'venue': zr_powered_room.location, 'inheriting': False},
    )

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 0, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 19, 0, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # delete event
    zr_event.delete('Unit test')

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_contrib(mock_tasks, dummy_room, zr_event, zr_contrib, zr_powered_room, another_zr_powered_room):
    tasks = mock_tasks()

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 0, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 0, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    tasks = mock_tasks()
    # change to a non-equipped room should trigger a DELETE
    update_contribution(
        zr_contrib,
        {
            'location_data': {'room': dummy_room, 'venue': dummy_room.location, 'inheriting': False},
        },
    )

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # a time change at this point (room not ZR-enabled) should not trigger anything
    with track_time_changes():
        update_contribution(zr_contrib, {'start_dt': datetime(2024, 3, 1, 17, 15, tzinfo=TZ)})

    tasks = mock_tasks()
    assert not next(tasks, None)

    # change to an equipped room should trigger a CREATE
    update_contribution(
        zr_contrib,
        {
            'location_data': {'room': zr_powered_room, 'venue': zr_powered_room.location, 'inheriting': False},
        },
    )

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 17, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # ... and this time change should trigger an UPDATE
    with track_time_changes():
        update_contribution(zr_contrib, {'start_dt': datetime(2024, 3, 1, 16, 25, tzinfo=TZ)})

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.update,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 25, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert not next(tasks, None)

    # change to an equally equipped room should trigger a MOVE
    update_contribution(
        zr_contrib,
        {
            'location_data': {
                'room': another_zr_powered_room,
                'venue': another_zr_powered_room.location,
                'inheriting': False,
            },
        },
    )

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.move,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 25, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': {'new_zr_id': 'test-zoom-room-2@example.com'},
    }
    assert not next(tasks, None)

    # delete the contribution, which should reattach the room to the event (DELETE + CREATE)
    delete_contribution(zr_contrib)

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-2@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-2@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 00, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 00, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert not next(tasks, None)

    # deleting the event should result in two DELETEs
    zr_event.delete('test')

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert not next(tasks, None)


def test_session_block(zr_event, mock_tasks, zr_session, zr_powered_room, another_zr_powered_room):
    (session, block_1, block_2, _contrib_1, contrib_2) = zr_session

    tasks = mock_tasks()

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': EVENT_ENTRY_ID,
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 0, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 0, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:block:1:zmeeting4',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    # contribution 2 is not in an equipped room, so there are no operations triggered
    # session block 2 is not in an equipped room, so there are no operations triggered
    assert not next(tasks, None)

    update_session_block(
        block_2,
        {
            'location_data': {
                'room': another_zr_powered_room,
                'venue': another_zr_powered_room.location,
                'inheriting': False,
            }
        },
    )

    # changing the room to another ZR-powered room should trigger CREATE for block and contribution
    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-2@example.com@indico:event:1:block:2:zmeeting5',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 17, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-2@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-2@example.com@indico:event:1:contribution:2:zmeeting3',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 17, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-2@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # move contrib_2 to top level
    move_timetable_entry(contrib_2.timetable_entry, day=zr_event.start_dt)

    # this should trigger a MOVE of contrib_2, as the event uses a different (equipped) room
    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.move,
        'entry_id': 'zoom_meeting:test-zoom-room-2@example.com@indico:event:1:contribution:2:zmeeting3',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 17, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 17, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-2@example.com',
        'extra_args': {'new_zr_id': 'test-zoom-room-1@example.com'},
    }
    assert not next(tasks, None)

    # now move to block 1, which is using the same room
    move_timetable_entry(contrib_2.timetable_entry, parent=block_1.timetable_entry)

    # as expected, no changes
    tasks = mock_tasks()
    assert not next(tasks, None)

    # deleting the session should attach the Zoom meetings to the event, triggering DELETE / CREATE
    delete_session(session)

    tasks = mock_tasks()

    entry_data = {
        'title': ENTRY_TITLE,
        'start_dt': datetime(2024, 3, 1, 16, 00, tzinfo=TZ).timestamp(),
        'end_dt': datetime(2024, 3, 1, 18, 00, tzinfo=TZ).timestamp(),
        'url': 'https://example.com/kitties',
    }

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:block:1:zmeeting4',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting4',
        'entry_data': entry_data,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-2@example.com@indico:event:1:block:2:zmeeting5',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-2@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting5',
        'entry_data': entry_data,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting2',
        'entry_data': entry_data,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:2:zmeeting3',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting3',
        'entry_data': entry_data,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert not next(tasks, None)


def test_move_between_blocks(mock_tasks, zr_session):
    # ignore all set up operations
    mock_tasks.reset()

    _session, block_1, block_2, contrib_1, _contrib_2 = zr_session

    # move contrib_1 to block_2
    move_timetable_entry(contrib_1.timetable_entry, parent=block_2.timetable_entry)

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)

    # move contrib_1 back to block_1
    move_timetable_entry(contrib_1.timetable_entry, parent=block_1.timetable_entry)

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 35, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_clone(zr_event, mock_tasks, zr_session, db_reset_seqs):
    # ignore all set up operations
    mock_tasks.reset()

    clone_event(
        zr_event, 1, datetime(2024, 4, 1, 9, 30, tzinfo=TZ), {'timetable', 'vc', 'event_location'}, Category.get(0)
    )

    tasks = mock_tasks()

    # only block_1 is in an ZR-ready room, so the clone of block_2 shouldn't be mentioned at all
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:2:zmeeting1',
        'entry_data': {
            'title': 'New Room',
            'start_dt': datetime(2024, 4, 1, 9, 30, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 4, 1, 11, 30, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:2:contribution:3:zmeeting2',
        'entry_data': {
            'title': 'New Room',
            'start_dt': datetime(2024, 4, 1, 9, 45, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 4, 1, 10, 5, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:2:block:4:zmeeting4',
        'entry_data': {
            'title': 'New Room',
            'start_dt': datetime(2024, 4, 1, 9, 45, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 4, 1, 10, 15, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_reassign(zr_event, zr_contrib, mock_tasks, test_client, no_csrf_check, zoom_api, db):
    # ignore all set up operations
    mock_tasks.reset()

    with test_client.session_transaction() as sess:
        sess.set_session_user(zoom_api['user'])
        # despite no_csrf_check, this is still needed since the form does its own
        sess['_csrf_token'] = 'supersecure'

    assoc = zr_contrib.vc_room_associations[0]

    # change assignment of association
    with db.session.no_autoflush:
        resp = test_client.post(
            f'/event/{zr_event.id}/manage/videoconference/zoom/{assoc.id}/',
            data={
                'vc-csrf_token': 'supersecure',
                'vc-linking': 'event',
            },
        )
        assert resp.status_code == 200

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.create,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 00, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 00, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_zoom_meeting_rename(zr_event, mock_tasks, test_client, no_csrf_check, zoom_api, db):
    # ignore all set up operations
    mock_tasks.reset()

    assoc = zr_event.vc_room_associations[0]

    with test_client.session_transaction() as sess:
        sess.set_session_user(zoom_api['user'])
        # despite no_csrf_check, this is still needed since the form does its own
        sess['_csrf_token'] = 'supersecure'

    # change assignment of association
    with db.session.no_autoflush:
        resp = test_client.post(
            f'/event/{zr_event.id}/manage/videoconference/zoom/{assoc.id}/',
            data={'vc-csrf_token': 'supersecure', 'vc-name': 'New name for meeting'},
        )
        assert resp.status_code == 200

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.update,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting1',
        'entry_data': {
            'title': 'New name for meeting',
            'start_dt': datetime(2024, 3, 1, 16, 00, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 18, 00, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_corner_case_update_no_room(zr_event, mock_tasks):
    # ignore all set up operations
    mock_tasks.reset()

    update_event(zr_event, location_data={'room': None, 'inheriting': False})

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.delete,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting1',
        'entry_data': None,
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }
    assert not next(tasks, None)


def test_corner_case_create_no_room(create_event, create_zoom_meeting, mock_tasks, zoom_api):
    event = create_event(
        creator=zoom_api['user'],
        creator_has_privileges=True,
        start_dt=datetime(2024, 3, 1, 16, 0, tzinfo=TZ),
        end_dt=datetime(2024, 3, 1, 18, 0, tzinfo=TZ),
        title='Test Event #1',
    )

    create_zoom_meeting(event, 'event')

    tasks = mock_tasks()
    assert not next(tasks, None)


def test_corner_case_timetable_expand(zr_contrib, mock_tasks, dummy_user, db):
    zr_contrib.event.end_dt = datetime(2024, 3, 1, 16, 35, tzinfo=TZ)
    zr_contrib.event.update_principal(dummy_user, full_access=True)
    mock_tasks.reset()

    # overflow the event by changing the contribution duration
    with track_time_changes(auto_extend=True, user=dummy_user):
        update_timetable_entry(zr_contrib.timetable_entry, {'duration': timedelta(minutes=30)})

    tasks = mock_tasks()
    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.update,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:contribution:1:zmeeting2',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 15, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert _entry_data(next(tasks)) == {
        'type': ZoomRoomsAction.update,
        'entry_id': 'zoom_meeting:test-zoom-room-1@example.com@indico:event:1:zmeeting1',
        'entry_data': {
            'title': ENTRY_TITLE,
            'start_dt': datetime(2024, 3, 1, 16, 00, tzinfo=TZ).timestamp(),
            'end_dt': datetime(2024, 3, 1, 16, 45, tzinfo=TZ).timestamp(),
            'url': 'https://example.com/kitties',
        },
        'zoom_room_id': 'test-zoom-room-1@example.com',
        'extra_args': None,
    }

    assert not next(tasks, None)
