"""Add request state table

Revision ID: 96ebe0eab248
Revises: 
Create Date: 2017-05-15 17:05:21.752213
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema

from indico.core.db.sqlalchemy import PyIntEnum

from indico_cern_access.models.access_requests import AccessRequestState


# revision identifiers, used by Alembic.
revision = '96ebe0eab248'
down_revision = None


def upgrade():
    op.execute(CreateSchema('plugin_cern_access'))
    op.create_table('access_requests',
                    sa.Column('registration_id', sa.Integer(), nullable=False),
                    sa.Column('request_state', PyIntEnum(AccessRequestState), nullable=False),
                    sa.Column('reservation_code', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['registration_id'], ['event_registration.registrations.id']),
                    sa.PrimaryKeyConstraint('registration_id'),
                    schema='plugin_cern_access')


def downgrade():
    op.drop_table('access_requests', schema='plugin_cern_access')
    op.execute(DropSchema('plugin_cern_access'))
