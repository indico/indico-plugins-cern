"""Make user-event-action non-unique

Revision ID: a8848e48dec
Revises: 4139aad72a1f
Create Date: 2015-03-04 13:46:31.178473
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'a8848e48dec'
down_revision = '4139aad72a1f'


def upgrade():
    op.drop_constraint('uq_outlook_queue_user_id_event_id_action', 'outlook_queue', schema='plugin_outlook')
    op.create_index('ix_user_event_action', 'outlook_queue', ['user_id', 'event_id', 'action'], unique=False,
                    schema='plugin_outlook')


def downgrade():
    op.drop_index('ix_user_event_action', table_name='outlook_queue', schema='plugin_outlook')
    op.create_unique_constraint('uq_outlook_queue_user_id_event_id_action', 'outlook_queue',
                                ['user_id', 'event_id', 'action'], schema='plugin_outlook')
