"""add new action

Revision ID: 636d44cb7a7c
Revises:
Create Date: 2024-11-15 20:50:19.477580

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '636d44cb7a7c'
down_revision = '6093a83228a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE plugin_outlook.queue DROP CONSTRAINT ck_queue_valid_enum_action')
    op.execute('ALTER TABLE plugin_outlook.queue ADD CONSTRAINT ck_queue_valid_enum_action CHECK (action IN (1, 2, 3, 4, 5))')


def downgrade() -> None:
    op.execute('ALTER TABLE plugin_outlook.queue DROP CONSTRAINT ck_queue_valid_enum_action')
    op.execute('ALTER TABLE plugin_outlook.queue ADD CONSTRAINT ck_queue_valid_enum_action CHECK (action IN (1, 2, 3, 4))')
