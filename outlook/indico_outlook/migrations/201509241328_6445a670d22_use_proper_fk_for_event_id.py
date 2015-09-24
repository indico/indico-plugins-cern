"""Use proper FK for event_id

Revision ID: 6445a670d22
Revises: 2dd6b41d0d19
Create Date: 2015-09-24 13:28:44.703336
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '6445a670d22'
down_revision = '2dd6b41d0d19'


def upgrade():
    op.create_foreign_key(None,
                          'queue', 'events',
                          ['event_id'], ['id'],
                          source_schema='plugin_outlook', referent_schema='events')


def downgrade():
    op.drop_constraint('fk_queue_event_id_events', 'queue', schema='plugin_outlook')
