"""Make reservation code unique

Revision ID: 92377810f14e
Revises: ee88b64f9494
Create Date: 2024-10-15 17:02:59.886902
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '92377810f14e'
down_revision = 'ee88b64f9494'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(None, 'access_requests', ['reservation_code'], schema='plugin_cern_access')


def downgrade():
    op.drop_constraint('uq_access_requests_reservation_code', 'access_requests', type_='unique', schema='plugin_cern_access')
