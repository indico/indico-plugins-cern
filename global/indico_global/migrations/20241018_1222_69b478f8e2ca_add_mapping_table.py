"""Add mapping table

Revision ID: 69b478f8e2ca
Revises:
Create Date: 2024-10-18 12:22:53.308233
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '69b478f8e2ca'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema('plugin_global'))
    op.create_table(
        'id_map',
        sa.Column('col', sa.String(), primary_key=True),
        sa.Column('local_id', sa.Integer(), primary_key=True),
        sa.Column('global_id', sa.Integer(), nullable=False),
        schema='plugin_global',
    )


def downgrade():
    op.drop_table('id_map', schema='plugin_global')
    op.execute(DropSchema('plugin_global'))
