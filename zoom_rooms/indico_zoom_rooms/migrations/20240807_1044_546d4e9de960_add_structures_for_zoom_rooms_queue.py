# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

"""Add structures for zoom rooms queue

Revision ID: 546d4e9de960
Revises:
Create Date: 2024-08-07 10:44:37.218268
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from indico.core.db.sqlalchemy import PyIntEnum
from indico.util.enum import IndicoIntEnum


# revision identifiers, used by Alembic.
revision = '546d4e9de960'
down_revision = None
branch_labels = None
depends_on = None


class _ZoomRoomsAction(IndicoIntEnum):
    create = 0
    update = 1
    move = 2
    delete = 3


def upgrade():
    op.execute(CreateSchema('plugin_zoom_rooms'))
    op.create_table(
        'queue',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('entry_id', sa.String(), nullable=False),
        sa.Column('zoom_room_id', sa.String(), nullable=False),
        sa.Column('action', PyIntEnum(_ZoomRoomsAction), nullable=False),
        sa.Column('entry_data', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column('extra_args', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(f'action != {_ZoomRoomsAction.delete} OR (entry_data IS NULL AND extra_args IS NULL)',
                           'delete_has_no_data'),
        sa.CheckConstraint(f'action = {_ZoomRoomsAction.delete} OR entry_data IS NOT NULL', 'other_actions_have_data'),
        sa.CheckConstraint(f'(action = {_ZoomRoomsAction.move}) = (extra_args IS NOT NULL)', 'only_move_has_extra_args'),
        schema='plugin_zoom_rooms',
    )


def downgrade():
    op.drop_table('queue', schema='plugin_zoom_rooms')
    op.execute(DropSchema('plugin_zoom_rooms'))
