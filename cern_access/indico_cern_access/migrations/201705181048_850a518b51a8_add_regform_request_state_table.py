"""add regform request state table

Revision ID: 850a518b51a8
Revises: 96ebe0eab248
Create Date: 2017-05-18 10:48:14.941535
"""

import sqlalchemy as sa
from alembic import op
from indico.core.db.sqlalchemy import PyIntEnum
from indico_cern_access.models.access_requests import AccessRequestState


# revision identifiers, used by Alembic.
revision = '850a518b51a8'
down_revision = '96ebe0eab248'


def upgrade():
    op.create_table('regform_access_requests',
                    sa.Column('form_id', sa.Integer(), nullable=False),
                    sa.Column('request_state', PyIntEnum(AccessRequestState), nullable=False),
                    sa.Column('allow_unpaid', sa.Boolean(), nullable=False),
                    sa.ForeignKeyConstraint(['form_id'], ['event_registration.forms.id']),
                    sa.PrimaryKeyConstraint('form_id'),
                    schema='plugin_cern_access')


def downgrade():
    op.drop_table('regform_access_requests', schema='plugin_cern_access')
