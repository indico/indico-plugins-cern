"""Create count_weekdays function

Revision ID: 564d660d4ddb
Revises:
Create Date: 2021-10-29 12:02:59.409012
"""

import textwrap

from alembic import op
from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '564d660d4ddb'
down_revision = None
branch_labels = None
depends_on = None


SQL_FUNCTION_COUNT_WEEKDAYS = textwrap.dedent('''
    CREATE FUNCTION plugin_burotel.count_weekdays(from_date date, to_date date)
        RETURNS bigint
    AS $$
        SELECT COUNT(*)
        FROM generate_series(from_date, to_date, '1 day'::interval) d
        WHERE extract('dow' FROM d) NOT IN (0, 6)
    $$
    LANGUAGE SQL IMMUTABLE STRICT;
''')


def upgrade():
    op.execute(CreateSchema('plugin_burotel'))
    op.execute(SQL_FUNCTION_COUNT_WEEKDAYS)


def downgrade():
    op.execute('DROP FUNCTION plugin_burotel.count_weekdays(from_date date, to_date date)')
    op.execute(DropSchema('plugin_burotel'))
