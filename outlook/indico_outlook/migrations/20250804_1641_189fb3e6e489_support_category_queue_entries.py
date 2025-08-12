"""Support category queue entries

Revision ID: 189fb3e6e489
Revises: 532798ae4e02
Create Date: 2025-08-04 16:41:11.447463
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '189fb3e6e489'
down_revision = '532798ae4e02'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('queue', sa.Column('category_id', sa.Integer(), nullable=True), schema='plugin_outlook')
    op.alter_column('queue', 'event_id', nullable=True, schema='plugin_outlook')
    op.create_index(None, 'queue', ['category_id'], unique=False, schema='plugin_outlook')
    op.create_foreign_key(None, 'queue', 'categories', ['category_id'], ['id'],
                          source_schema='plugin_outlook', referent_schema='categories')
    op.create_check_constraint('no_category_updates', 'queue', '(action != 2) OR (category_id IS NULL)',
                               schema='plugin_outlook')
    op.create_check_constraint('event_xor_category', 'queue', '(event_id IS NULL) != (category_id IS NULL)',
                               schema='plugin_outlook')


def downgrade():
    op.execute('DELETE FROM plugin_outlook.queue WHERE event_id IS NULL')
    op.drop_constraint('ck_queue_no_category_updates', 'queue', schema='plugin_outlook')
    op.drop_constraint('ck_queue_event_xor_category', 'queue', schema='plugin_outlook')
    op.alter_column('queue', 'event_id', nullable=False, schema='plugin_outlook')
    op.drop_column('queue', 'category_id', schema='plugin_outlook')
