"""Update user setting

Revision ID: da9deaa182a4
Revises: 6093a83228a7
Create Date: 2024-11-17 11:13:13.705549
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'da9deaa182a4'
down_revision = '6093a83228a7'
branch_labels = None
depends_on = None


def upgrade():
    # Rename status_overrides to overrides
    op.execute('''
        UPDATE users.settings
        SET name = 'overrides'
        WHERE module = 'plugin_outlook' AND name = 'status_overrides'
    ''')
    # Add the default settings
    op.execute('''
        UPDATE users.settings
        SET value = (
            SELECT jsonb_agg(
                elem || '{"reminder": true, "reminder_minutes": 15}'
            )
            FROM jsonb_array_elements(value) AS elem
        )
        WHERE module = 'plugin_outlook' AND name = 'overrides'
    ''')


def downgrade():
    # Remove the default settings
    op.execute('''
        UPDATE users.settings
        SET value = (
            SELECT jsonb_agg(
                elem - 'reminder' - 'reminder_minutes'
            )
            FROM jsonb_array_elements(value) AS elem
        )
        WHERE module = 'plugin_outlook' AND name = 'overrides'
    ''')
    # Rename the field back to status_overrides
    op.execute('''
        UPDATE users.settings
        SET name = 'status_overrides'
        WHERE module = 'plugin_outlook' AND name = 'overrides'
    ''')
