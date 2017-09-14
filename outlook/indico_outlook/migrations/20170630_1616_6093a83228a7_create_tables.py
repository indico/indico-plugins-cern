"""Create tables

Revision ID: 6093a83228a7
Revises:
Create Date: 2017-06-30 16:16:52.276112
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from indico.core.db.sqlalchemy import PyIntEnum

from indico_outlook.models.queue import OutlookAction


# revision identifiers, used by Alembic.
revision = '6093a83228a7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema('plugin_outlook'))
    op.create_table('queue',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False, index=True),
                    sa.Column('event_id', sa.Integer(), nullable=False, index=True),
                    sa.Column('action', PyIntEnum(OutlookAction), nullable=False),
                    sa.ForeignKeyConstraint(['event_id'], ['events.events.id']),
                    sa.ForeignKeyConstraint(['user_id'], ['users.users.id']),
                    sa.PrimaryKeyConstraint('id'),
                    schema='plugin_outlook')
    op.create_index(None, 'queue', ['user_id', 'event_id', 'action'], schema='plugin_outlook')


def downgrade():
    op.drop_table('queue', schema='plugin_outlook')
    op.execute(DropSchema('plugin_outlook'))
