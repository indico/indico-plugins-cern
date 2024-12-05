# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import textwrap

from sqlalchemy import DDL, text
from sqlalchemy.event import listens_for
from sqlalchemy.sql.ddl import CreateSchema

from indico.core import signals
from indico.core.db import db
from indico.core.db.sqlalchemy.core import _schema_exists


SCHEMA_NAME = 'plugin_labotel'
SQL_FUNCTION_COUNT_WEEKDAYS = textwrap.dedent('''
    CREATE FUNCTION plugin_labotel.count_weekdays(from_date date, to_date date)
        RETURNS bigint
    AS $$
        SELECT COUNT(*)
        FROM generate_series(from_date, to_date, '1 day'::interval) d
        WHERE extract('dow' FROM d) NOT IN (0, 6)
    $$
    LANGUAGE SQL IMMUTABLE STRICT;
''')


def _should_create_function(ddl, target, connection, **kw):
    sql = '''
        SELECT COUNT(*)
        FROM information_schema.routines
        WHERE routine_schema = 'plugin_labotel' AND routine_name = 'count_weekdays'
    '''
    count = connection.execute(text(sql)).scalar()
    return not count


@listens_for(db.Model.metadata, 'before_create')
def _create_plugin_schema(target, connection, **kw):
    # We do not have any actual models, so we have to manually create our schema...
    if not _schema_exists(connection, SCHEMA_NAME):
        CreateSchema(SCHEMA_NAME).execute(connection)
        signals.core.db_schema_created.send(SCHEMA_NAME, connection=connection)


@signals.core.db_schema_created.connect_via(SCHEMA_NAME)
def _create_count_weekdays_func(sender, connection, **kwargs):
    DDL(SQL_FUNCTION_COUNT_WEEKDAYS).execute_if(callable_=_should_create_function).execute(connection)
