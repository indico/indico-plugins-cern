"""Add entries table

Revision ID: 532798ae4e02
Revises: da9deaa182a4
Create Date: 2025-07-28 12:18:51.599781
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '532798ae4e02'
down_revision = 'da9deaa182a4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'entries',
        sa.Column('user_id', sa.Integer(), primary_key=True, index=True),
        sa.Column('event_id', sa.Integer(), primary_key=True, index=True),
        sa.Column('calendar_entry_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.events.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.users.id']),
        schema='plugin_outlook',
    )


def downgrade():
    op.drop_table('entries', schema='plugin_outlook')
