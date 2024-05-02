# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import itertools

from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, rrule
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import bindparam

from indico.core.db import db
from indico.modules.rb.models.reservations import Reservation, ReservationOccurrence
from indico.modules.rb.models.rooms import Room
from indico.util.string import natural_sort_key


def _build_per_building_query(*query_results):
    return (db.session
            .query(*query_results)
            .select_from(ReservationOccurrence)
            .filter(Room.is_reservable, ~Room.is_deleted)
            .filter(ReservationOccurrence.is_valid, Reservation.is_accepted)
            .join(Reservation)
            .join(Room)
            .group_by(Room.building, Room.division))


def calculate_monthly_stats(start_dt, end_dt):
    """Calculate monthly stats for the Labotel system, based on a date range."""

    room = aliased(Room)
    months = list(rrule(freq=MONTHLY, dtstart=start_dt, until=end_dt))

    desk_count = (db.session.query(db.func.count(room.id))
                  .filter(
                      Room.building == room.building,
                      Room.division == room.division,
                      room.is_reservable,
                      ~room.is_deleted)
                  ).label('desk_count')

    # a first query which retrieves building data as well as the total number of bookings
    building_query = _build_per_building_query(
        Room.building.label('number'),
        Room.division.label('experiment'),
        desk_count,
        db.func.count(
            db.func.concat(Reservation.id, ReservationOccurrence.start_dt)).label('bookings')
    ).filter(ReservationOccurrence.start_dt >= start_dt, ReservationOccurrence.end_dt <= end_dt).order_by('number')

    parts = []
    for n, month_start in enumerate(months):
        month_end = (month_start + relativedelta(months=1, days=-1)).replace(hour=23, minute=59)
        parts.append(
            _build_per_building_query(
                Room.building.label('number'),
                Room.division.label('experiment'),
                bindparam(f'month-{n}', n).label('month'),
                db.func.count(db.func.concat(Reservation.id, ReservationOccurrence.start_dt)).label('bookings')
            ).filter(ReservationOccurrence.start_dt >= month_start, ReservationOccurrence.end_dt <= month_end)
        )

    # create a union with all month queries. this will return a (second) query which will provide
    # separate totals for each month
    month_query = parts[0].union(*parts[1:])

    # rearrange the returned rows in a more processable format
    bldg_exp_map = [
        ((building, experiment), {'bookings': bookings, 'desk_count': count, 'months': [0] * len(months)})
        for building, experiment, count, bookings in building_query
    ]

    # convert the previous list in to a nested dict object
    bldg_map = {
        k: {bldg_exp[1]: data for bldg_exp, data in v}
        for k, v in itertools.groupby(
            bldg_exp_map,
            lambda w: w[0][0]
        )
    }

    # merge the "month query" into the "building query"
    for number, experiment, month, bookings in month_query:
        bldg_map[number][experiment]['months'][month] = bookings

    # this is a third query which adds in buildings/experiments not matched in the previous ones
    unmatched_query = (db.session
                       .query(Room.building, Room.division, desk_count)
                       .filter(Room.is_reservable, ~Room.is_deleted)
                       .group_by(Room.building, Room.division))

    # let's add all "unmatched" buildings/experiments with zeroed totals
    for building, experiment, desk_count in unmatched_query:
        if not bldg_map.get(building, {}).get(experiment):
            bldg_map.setdefault(building, {})
            bldg_map[building][experiment] = {
                'bookings': 0,
                'desk_count': desk_count,
                'months': [0] * len(months)
            }

    # resulted sorted by building/experiment
    result = [(number, sorted(v.items()))
              for number, v in sorted(bldg_map.items(), key=lambda x: natural_sort_key(x[0]))]

    return result, months
