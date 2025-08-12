"""Allow queue entries without user

Revision ID: f166c1593d5e
Revises: 189fb3e6e489
Create Date: 2025-08-06 17:48:08.619145
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'f166c1593d5e'
down_revision = '189fb3e6e489'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('queue', 'user_id', nullable=True, schema='plugin_outlook')


def downgrade():
    op.execute('DELETE FROM plugin_outlook.queue WHERE user_id IS NULL')
    op.alter_column('queue', 'user_id', nullable=False, schema='plugin_outlook')
