"""Add startup assistance requests table

Revision ID: b160812c186b
Revises:
Create Date: 2019-02-20 11:38:08.691528
"""

from __future__ import unicode_literals

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = 'b160812c186b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema('plugin_room_assistance'))
    op.create_table(
        'room_assistance_requests',
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['reservation_id'], ['roombooking.reservations.id']),
        sa.PrimaryKeyConstraint('reservation_id'),
        schema='plugin_room_assistance'
    )

    conn = op.get_bind()
    conn.execute('''
        INSERT INTO plugin_room_assistance.room_assistance_requests
        SELECT id FROM roombooking.reservations WHERE needs_assistance
    ''')

    conn.execute('''
        UPDATE settings SET module = 'plugin_room_assistance', name = 'room_assistance_recipients'
        WHERE module = 'plugin_cronjobs_cern' AND name = 'startup_assistance_recipients'
    ''')
    conn.execute('''
        UPDATE settings SET module = 'plugin_room_assistance'
        WHERE module = 'plugin_cronjobs_cern'
        AND name IN ('rooms', 'reservation_rooms', 'categories', 'conf_room_recipients')
    ''')
    conn.execute('''
        INSERT INTO settings (module, name, value)
        VALUES (
            'plugin_room_assistance',
            'rooms_with_assistance',
            array_to_json(ARRAY(SELECT id FROM roombooking.rooms WHERE notification_for_assistance))
        )
    ''')


def downgrade():
    conn = op.get_bind()
    conn.execute('''
        UPDATE roombooking.reservations SET needs_assistance = TRUE
        WHERE id IN (SELECT reservation_id FROM plugin_room_assistance.room_assistance_requests)
    ''')
    conn.execute('''
        UPDATE roombooking.rooms SET notification_for_assistance = TRUE
        WHERE id::TEXT IN (
            SELECT json_array_elements_text(value) FROM settings
            WHERE module = 'plugin_room_assistance' AND name = 'rooms_with_assistance'
        )
    ''')

    conn.execute('''
        UPDATE settings SET module = 'plugin_cronjobs_cern', name = 'startup_assistance_recipients'
        WHERE module = 'plugin_room_assistance' AND name = 'room_assistance_recipients'
    ''')
    conn.execute('''
        UPDATE settings SET module = 'plugin_cronjobs_cern'
        WHERE module = 'plugin_room_assistance'
        AND name IN ('rooms', 'reservation_rooms', 'categories', 'conf_room_recipients')
    ''')
    conn.execute("DELETE FROM settings WHERE module = 'plugin_room_assistance' and name = 'rooms_with_assistance'")

    op.drop_table('room_assistance_requests', schema='plugin_room_assistance')
    op.execute(DropSchema('plugin_room_assistance'))
