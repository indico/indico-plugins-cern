"""Add license plate field

Revision ID: f46cd5b57a7a
Revises: 96ebe0eab248
Create Date: 2019-07-05 16:16:42.151911
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f46cd5b57a7a'
down_revision = '96ebe0eab248'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'access_requests',
        sa.Column('license_plate', sa.String(), nullable=True),
        schema='plugin_cern_access'
    )


def downgrade():
    op.drop_column(
        'access_requests',
        'license_plate',
        schema='plugin_cern_access'
    )
