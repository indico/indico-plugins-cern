"""Create tables

Revision ID: 4139aad72a1f
Revises: None
Create Date: 2014-10-10 11:32:42.971904
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from indico.core.db.sqlalchemy import PyIntEnum

from indico_outlook.models.queue import OutlookAction

# revision identifiers, used by Alembic.
revision = '4139aad72a1f'
down_revision = None


def upgrade():
    op.execute(CreateSchema('plugin_outlook'))
    op.create_table('outlook_queue',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('event_id', sa.Integer(), nullable=False, index=True),
                    sa.Column('action', PyIntEnum(OutlookAction), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('user_id', 'event_id', 'action'),
                    schema='plugin_outlook')
    op.create_table('outlook_blacklist',
                    sa.Column('user_id', sa.Integer(), autoincrement=False, nullable=False),
                    sa.PrimaryKeyConstraint('user_id'),
                    schema='plugin_outlook')


def downgrade():
    op.drop_table('outlook_blacklist', schema='plugin_outlook')
    op.drop_table('outlook_queue', schema='plugin_outlook')
    op.execute(DropSchema('plugin_outlook'))
