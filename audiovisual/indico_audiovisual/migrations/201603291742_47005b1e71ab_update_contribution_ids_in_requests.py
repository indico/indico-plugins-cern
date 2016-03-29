"""Update contribution ids in requests

Revision ID: 47005b1e71ab
Revises: 429c381aa08f
Create Date: 2016-03-29 17:42:39.416279
"""

import json

from alembic import context, op


# revision identifiers, used by Alembic.
revision = '47005b1e71ab'
down_revision = '429c381aa08f'


contrib_query = """
    SELECT contribution_id
    FROM events.legacy_contribution_id_map
    WHERE event_id = %s AND legacy_contribution_id = %s
"""

contrib_query_down = """
    SELECT legacy_contribution_id
    FROM events.legacy_contribution_id_map
    WHERE event_id = %s AND contribution_id = %s
"""

subcontrib_query = """
    SELECT subcontribution_id
    FROM events.legacy_subcontribution_id_map
    WHERE event_id = %s AND legacy_contribution_id = %s AND legacy_subcontribution_id = %s
"""

subcontrib_query_down = """
    SELECT legacy_contribution_id, legacy_subcontribution_id
    FROM events.legacy_subcontribution_id_map
    WHERE event_id = %s AND subcontribution_id = %s
"""


def _legacy_to_new(conn, event_id, ids):
    for id_ in ids:
        assert ':' not in id_
        if '-' in id_:
            parts = id_.split('-')
            res = conn.execute(subcontrib_query, (event_id, parts[0], parts[1])).fetchone()
            if not res:
                print 'not found: {}/{}-{}'.format(event_id, parts[0], parts[1])
                continue
            yield 'sc:{}'.format(res[0])
        else:
            res = conn.execute(contrib_query, (event_id, id_)).fetchone()
            if not res:
                print 'not found: {}/{}'.format(event_id, id_)
                continue
            yield 'c:{}'.format(res[0])


def _new_to_legacy(conn, event_id, ids):
    for id_ in ids:
        type_, obj_id = id_.split(':', 1)
        if type_ == 'c':
            res = conn.execute(contrib_query_down, (event_id, obj_id)).fetchone()
            yield unicode(res[0])
        elif type_ == 'sc':
            res = conn.execute(subcontrib_query_down, (event_id, obj_id)).fetchone()
            yield '{}-{}'.format(*res)
        else:
            raise ValueError('invalid type: ' + type_)


def _iter_requests(conn):
    res = conn.execute("SELECT id, event_id, data FROM events.requests WHERE type = 'webcast-recording'")
    for id_, event_id, data in res:
        if data.get('contributions'):
            yield id_, event_id, data


def _update_data(conn, id_, data):
    conn.execute("UPDATE events.requests SET data = %s WHERE id = %s", (json.dumps(data), id_))


def upgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')
    conn = op.get_bind()
    for id_, event_id, data in _iter_requests(conn):
        data['contributions'] = list(_legacy_to_new(conn, event_id, data['contributions']))
        _update_data(conn, id_, data)


def downgrade():
    if context.is_offline_mode():
        raise Exception('This downgrade is only possible in online mode')
    conn = op.get_bind()
    for id_, event_id, data in _iter_requests(conn):
        data['contributions'] = list(_new_to_legacy(conn, event_id, data['contributions']))
        _update_data(conn, id_, data)
