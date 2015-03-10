"""Remove table name prefix

Revision ID: 3110636a18e4
Revises: a8848e48dec
Create Date: 2015-03-10 16:10:00.498686
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '3110636a18e4'
down_revision = 'a8848e48dec'


def upgrade():
    op.rename_table('outlook_blacklist', 'blacklist', schema='plugin_outlook')
    op.rename_table('outlook_queue', 'queue', schema='plugin_outlook')
    op.execute('ALTER SEQUENCE "plugin_outlook"."outlook_queue_id_seq" RENAME TO "queue_id_seq"')


def downgrade():
    op.execute('ALTER SEQUENCE "plugin_outlook"."queue_id_seq" RENAME TO "outlook_queue_id_seq"')
    op.rename_table('queue', 'outlook_queue', schema='plugin_outlook')
    op.rename_table('blacklist', 'outlook_blacklist', schema='plugin_outlook')
