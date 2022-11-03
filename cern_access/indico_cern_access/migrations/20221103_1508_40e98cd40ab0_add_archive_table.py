"""Add archive table

Revision ID: 40e98cd40ab0
Revises: e90cc0f72adc
Create Date: 2022-11-03 15:08:38.415396
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '40e98cd40ab0'
down_revision = 'e90cc0f72adc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'archived_access_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False, index=True),
        sa.Column('registration_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=False),
        sa.Column('nationality', sa.String(), nullable=False),
        sa.Column('birth_place', sa.String(), nullable=False),
        sa.Column('license_plate', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.events.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='plugin_cern_access'
    )


def downgrade():
    op.drop_table('archived_access_requests', schema='plugin_cern_access')
