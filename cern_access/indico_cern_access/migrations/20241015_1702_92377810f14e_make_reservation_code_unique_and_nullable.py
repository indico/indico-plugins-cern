"""Make reservation code unique and nullable

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
    op.alter_column('access_requests', 'reservation_code', nullable=True, schema='plugin_cern_access')
    op.execute('''
        UPDATE plugin_cern_access.access_requests
        SET reservation_code = NULL WHERE reservation_code = ''
    ''')
    op.create_unique_constraint(None, 'access_requests', ['reservation_code'], schema='plugin_cern_access')


def downgrade():
    op.drop_constraint('uq_access_requests_reservation_code', 'access_requests', schema='plugin_cern_access')
    op.execute('''
        UPDATE plugin_cern_access.access_requests
        SET reservation_code = '' WHERE reservation_code IS NULL
    ''')
    op.alter_column('access_requests', 'reservation_code', nullable=False, schema='plugin_cern_access')
