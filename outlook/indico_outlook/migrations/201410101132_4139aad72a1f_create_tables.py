"""Create tables

Revision ID: 4139aad72a1f
Revises: None
Create Date: 2014-10-10 11:32:42.971904
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '4139aad72a1f'
down_revision = None


def upgrade():
    op.execute(CreateSchema('plugin_outlook'))
    op.create_table('outlook_queue',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('event_id', sa.Integer(), nullable=False),
                    sa.Column('action', sa.SmallInteger(), nullable=False),
                    sa.CheckConstraint('action IN (1, 2, 3)'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('user_id', 'event_id', 'action'),
                    schema='plugin_outlook')


def downgrade():
    op.drop_table('outlook_queue', schema='plugin_outlook')
    op.execute(DropSchema('plugin_outlook'))
