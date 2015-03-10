"""Apply naming convention

Revision ID: 4c75e0c79387
Revises: 3110636a18e4
Create Date: 2015-03-10 16:13:39.740779
"""

from alembic import op

from indico.core.db.sqlalchemy.util.bulk_rename import bulk_rename


# revision identifiers, used by Alembic.
revision = '4c75e0c79387'
down_revision = '3110636a18e4'


mapping = {
    'plugin_outlook.blacklist': {
        'indexes': {
            'outlook_blacklist_pkey': 'pk_blacklist',
        }
    },
    'plugin_outlook.queue': {
        'indexes': {
            'outlook_queue_pkey': 'pk_queue',
            'ix_plugin_outlook_outlook_queue_event_id': 'ix_queue_event_id',
            'ix_user_event_action': 'ix_queue_user_id_event_id_action',
        },
        'constraints': {
            'outlook_queue_action_check': 'ck_queue_valid_enum_action',
        }
    }
}


def upgrade():
    for stmt in bulk_rename(mapping):
        op.execute(stmt)


def downgrade():
    for stmt in bulk_rename(mapping, True):
        op.execute(stmt)
