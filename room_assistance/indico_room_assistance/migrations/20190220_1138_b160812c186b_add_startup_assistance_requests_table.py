"""Add room assistance requests table

Revision ID: b160812c186b
Revises:
Create Date: 2019-02-20 11:38:08.691528
"""

from __future__ import print_function, unicode_literals

from alembic import context, op
from terminaltables import AsciiTable


# revision identifiers, used by Alembic.
revision = 'b160812c186b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')

    conn = op.get_bind()
    conn.execute('''
        INSERT INTO events.requests (event_id, type, state, data, created_by_id, created_dt)
        SELECT
            rvl.linked_event_id,
            'room-assistance',
            1,
            json_build_object('start_dt', rv.start_dt, 'reason', ''),
            (SELECT id FROM users.users WHERE is_system),
            rv.start_dt
        FROM roombooking.reservations rv
        JOIN roombooking.reservation_links rvl ON rv.link_id = rvl.id AND rvl.link_type = 2
        WHERE rv.needs_assistance
    ''')

    invalid_reservations = conn.execute('''
        SELECT
            rv.id,
            rv.room_id,
            format('%%s/%%s-%%s', r.building, r.floor, r.number),
            rv.start_dt,
            rv.end_dt,
            rv.booked_for_name
        FROM roombooking.reservations rv
        JOIN roombooking.rooms r ON r.id = rv.room_id
        LEFT JOIN roombooking.reservation_links rvl ON rv.link_id = rvl.id
        WHERE rv.needs_assistance
        AND (rv.link_id IS NULL OR rvl.link_type != 2)
        AND rv.start_dt > NOW()
    ''')

    table_data = [['ID', 'Room ID', 'Room name', 'Start date', 'End date', 'Booked for']]
    for resv in invalid_reservations:
        table_data.append(list(resv))

    if len(table_data) > 1:
        print(AsciiTable(table_data,
                         'Reservations without a link to an event that need assistance in the future').table)

    conn.execute('''
        UPDATE indico.settings SET module = 'plugin_room_assistance', name = 'room_assistance_recipients'
        WHERE module = 'plugin_cronjobs_cern' AND name = 'startup_assistance_recipients'
    ''')
    conn.execute('''
        DELETE FROM indico.settings
        WHERE module = 'plugin_cronjobs_cern'
        AND name IN ('rooms', 'reservation_rooms', 'categories', 'conf_room_recipients')
    ''')
    conn.execute('''
        INSERT INTO indico.settings (module, name, value)
        VALUES (
            'plugin_room_assistance',
            'rooms_with_assistance',
            array_to_json(ARRAY(SELECT id FROM roombooking.rooms WHERE notification_for_assistance))
        )
    ''')


def downgrade():
    conn = op.get_bind()
    conn.execute('''
        UPDATE roombooking.rooms SET notification_for_assistance = TRUE
        WHERE id::TEXT IN (
            SELECT json_array_elements_text(value) FROM indico.settings
            WHERE module = 'plugin_room_assistance' AND name = 'rooms_with_assistance'
        )
    ''')

    conn.execute('''
        UPDATE indico.settings SET module = 'plugin_cronjobs_cern', name = 'startup_assistance_recipients'
        WHERE module = 'plugin_room_assistance' AND name = 'room_assistance_recipients'
    ''')
    conn.execute('''
        DELETE FROM indico.settings
        WHERE module = 'plugin_room_assistance' and name = 'rooms_with_assistance'
    ''')
