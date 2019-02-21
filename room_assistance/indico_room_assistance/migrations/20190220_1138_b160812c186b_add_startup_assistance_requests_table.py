"""Add startup assistance requests table

Revision ID: b160812c186b
Revises:
Create Date: 2019-02-20 11:38:08.691528
"""

from __future__ import unicode_literals

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = 'b160812c186b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')

    op.execute(CreateSchema('plugin_room_assistance'))
    op.create_table(
        'room_assistance_requests',
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['reservation_id'], ['roombooking.reservations.id']),
        sa.PrimaryKeyConstraint('reservation_id'),
        schema='plugin_room_assistance'
    )

    conn = op.get_bind()
    res = conn.execute('''
        SELECT id FROM roombooking.reservations
        WHERE needs_assistance
        AND end_dt > NOW()::TIMESTAMP
        AND state IN (1, 2)
    ''')
    for row in res:
        conn.execute('''
            INSERT INTO plugin_room_assistance.room_assistance_requests
            VALUES (%s)
        ''', (row.id,))

    op.drop_column('reservations', 'needs_assistance', schema='roombooking')


def downgrade():
    if context.is_offline_mode():
        raise Exception('This downgrade is only possible in online mode')

    op.add_column('reservations',
                  sa.Column('needs_assistance', sa.Boolean(), nullable=False, server_default='false'),
                  schema='roombooking')

    conn = op.get_bind()
    res = conn.execute('SELECT reservation_id FROM plugin_room_assistance.room_assistance_requests')
    for row in res:
        resv = conn.execute('SELECT TRUE FROM roombooking.reservations WHERE id = %s', (row.reservation_id,)).scalar()
        if not bool(resv):
            continue
        conn.execute('UPDATE roombooking.reservations SET needs_assistance = TRUE WHERE id = %s', (row.reservation_id,))

    op.drop_table('room_assistance_requests', schema='plugin_room_assistance')
    op.execute(DropSchema('plugin_room_assistance'))
