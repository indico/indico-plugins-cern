"""Add birth-related columns

Revision ID: f5eeaf2a9b92
Revises: 96ebe0eab248
Create Date: 2017-10-26 15:00:39.461191
"""

from __future__ import unicode_literals

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f5eeaf2a9b92'
down_revision = u'96ebe0eab248'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('access_requests', sa.Column('birth_date', sa.Date()), schema='plugin_cern_access')
    op.add_column('access_requests', sa.Column('birth_country', sa.String()), schema='plugin_cern_access')
    op.add_column('access_requests', sa.Column('birth_city', sa.String()), schema='plugin_cern_access')


def downgrade():
    op.drop_column('access_requests', 'birth_date', schema='plugin_cern_access')
    op.drop_column('access_requests', 'birth_country', schema='plugin_cern_access')
    op.drop_column('access_requests', 'birth_city', schema='plugin_cern_access')
