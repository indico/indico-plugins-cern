"""Use FK for user_id and move blacklist to settings

Revision ID: 2dd6b41d0d19
Revises: 4c75e0c79387
Create Date: 2015-05-08 15:12:46.381533
"""

import sqlalchemy as sa
from alembic import context, op


# revision identifiers, used by Alembic.
revision = '2dd6b41d0d19'
down_revision = '4c75e0c79387'


def upgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')
    conn = op.get_bind()

    res = conn.execute('SELECT user_id FROM plugin_outlook.blacklist')
    for user_id, in res:
        conn.execute('INSERT INTO users.settings (module, name, value, user_id) VALUES (%s, %s, %s, %s)',
                     ('plugin_outlook', 'enabled', 'false', user_id))

    op.create_foreign_key(None,
                          'queue', 'users',
                          ['user_id'], ['id'],
                          source_schema='plugin_outlook', referent_schema='users')
    op.create_index(None, 'queue', ['user_id'], unique=False, schema='plugin_outlook')
    op.drop_table('blacklist', schema='plugin_outlook')


def downgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')
    conn = op.get_bind()

    op.create_table('blacklist',
                    sa.Column('user_id', sa.Integer(), autoincrement=False, nullable=False),
                    sa.PrimaryKeyConstraint('user_id'),
                    schema='plugin_outlook')

    res = conn.execute('SELECT user_id, value FROM users.settings WHERE module = %s AND name = %s',
                       ('plugin_outlook', 'enabled'))
    for user_id, value in res:
        if not value:
            conn.execute('INSERT INTO plugin_outlook.blacklist (user_id) VALUES (%s)', (user_id,))
    conn.execute('DELETE FROM users.settings WHERE module = %s AND name = %s', ('plugin_outlook', 'enabled'))

    op.drop_index(op.f('ix_queue_user_id'), table_name='queue', schema='plugin_outlook')
    op.drop_constraint('fk_queue_user_id_users', 'queue', schema='plugin_outlook')
