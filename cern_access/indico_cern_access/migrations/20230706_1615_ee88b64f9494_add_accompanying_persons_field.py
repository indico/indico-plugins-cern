"""Add accompanying persons field

Revision ID: ee88b64f9494
Revises: 40e98cd40ab0
Create Date: 2023-07-06 16:15:50.255420
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'ee88b64f9494'
down_revision = '40e98cd40ab0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'access_requests',
        sa.Column('accompanying_persons', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        schema='plugin_cern_access'
    )
    op.alter_column('access_requests', 'accompanying_persons', server_default=None, schema='plugin_cern_access')
    op.add_column(
        'archived_access_requests',
        sa.Column('accompanying_persons', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        schema='plugin_cern_access'
    )
    op.alter_column('archived_access_requests', 'accompanying_persons', server_default=None,
                    schema='plugin_cern_access')


def downgrade():
    op.drop_column('access_requests', 'accompanying_persons', schema='plugin_cern_access')
    op.drop_column('archived_access_requests', 'accompanying_persons', schema='plugin_cern_access')
