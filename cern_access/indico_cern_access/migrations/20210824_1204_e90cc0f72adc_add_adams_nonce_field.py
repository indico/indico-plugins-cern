"""Add adams_nonce field

Revision ID: e90cc0f72adc
Revises: f46cd5b57a7a
Create Date: 2021-08-24 12:04:15.167910
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e90cc0f72adc'
down_revision = 'f46cd5b57a7a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('access_requests',
                  sa.Column('adams_nonce', sa.String(), nullable=False, server_default=''),
                  schema='plugin_cern_access')
    op.alter_column('access_requests', 'adams_nonce', server_default=None, schema='plugin_cern_access')


def downgrade():
    op.drop_column('access_requests', 'adams_nonce', schema='plugin_cern_access')
