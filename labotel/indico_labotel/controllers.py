# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from dateutil.relativedelta import relativedelta
from flask import jsonify, session
from webargs import fields, validate
from webargs.flaskparser import use_kwargs

from indico.modules.rb.controllers import RHRoomBookingBase
from indico.util.date_time import format_datetime
from indico.util.spreadsheets import send_csv
from indico.web.rh import RHProtected
from indico.web.views import WPNewBase

from indico_labotel import _
from indico_labotel.util import calculate_monthly_stats


def get_month_dates(start_month, end_month):
    start_dt = start_month.replace(day=1, hour=0, minute=0)
    end_dt = end_month.replace(hour=23, minute=59) + relativedelta(months=1, days=-1)
    return start_dt, end_dt


class WPLabotelBase(WPNewBase):
    template_prefix = 'rb/'
    title = _('Labotel')
    bundles = ('common.js', 'common.css', 'react.js', 'react.css', 'jquery.js', 'semantic-ui.js', 'semantic-ui.css')


class RHLanding(RHRoomBookingBase):
    def _process(self):
        return WPLabotelBase.display('room_booking.html')


class RHUserDivision(RHProtected):
    def _process_GET(self):
        from indico_labotel.plugin import LabotelPlugin
        return jsonify(value=LabotelPlugin.user_settings.get(session.user, 'default_division'))

    @use_kwargs({
        'value': fields.String(validate=validate.OneOf({'Laser', 'Clean Room', 'DSF', 'QART'}), allow_none=True)
    })
    def _process_POST(self, value):
        from indico_labotel.plugin import LabotelPlugin
        LabotelPlugin.user_settings.set(session.user, 'default_division', value)


class RHLabotelStats(RHProtected):
    @use_kwargs({
        'start_month': fields.DateTime('%Y-%m'),
        'end_month': fields.DateTime('%Y-%m')
    }, location='query')
    def process(self, start_month, end_month):
        start_dt, end_dt = get_month_dates(start_month, end_month)
        result, months = calculate_monthly_stats(start_dt, end_dt)
        # number of days within the boundary dates (inclusive)
        num_days = ((end_dt - start_dt).days + 1)

        return jsonify(
            data=result,
            num_days=num_days,
            months=[{
                'name': format_datetime(m, 'MMMM YYYY', locale=session.lang),
                'id': format_datetime(m, 'YYYY-M'),
                'num_days': ((m + relativedelta(months=1, days=-1)) - m).days + 1
            } for m in months]
        )


class RHLabotelStatsCSV(RHProtected):
    @use_kwargs({
        'start_month': fields.DateTime('%Y-%m'),
        'end_month': fields.DateTime('%Y-%m')
    }, location='query')
    def process(self, start_month, end_month):
        start_dt, end_dt = get_month_dates(start_month, end_month)
        result, months = calculate_monthly_stats(start_dt, end_dt)
        # number of days within the boundary dates (inclusive)
        num_days = ((end_dt - start_dt).days + 1)

        headers = ['Building', 'Category', 'Number of labs']
        for m in months:
            headers += [m.strftime('%b %Y'), m.strftime('%b %Y (%%)')]
        headers.append('Total')
        headers.append('Total (%)')

        rows = []
        for building, experiments in result:
            for experiment, row_data in experiments:
                row = {
                    'Building': building,
                    'Category': experiment,
                    'Number of labs': row_data['desk_count']
                }
                for i, m in enumerate(row_data['months']):
                    month_dt = months[i]
                    month_duration = ((months[i] + relativedelta(months=1, days=-1)) - months[i]).days + 1
                    percent = float(m) / (row_data['desk_count'] * month_duration) * 100
                    row[month_dt.strftime('%b %Y')] = m
                    row[month_dt.strftime('%b %Y (%%)')] = f'{percent:.2f}%'
                row['Total'] = row_data['bookings']
                percent = float(row_data['bookings']) / (row_data['desk_count'] * num_days) * 100
                row['Total (%)'] = f'{percent:.2f}%'
                rows.append(row)
        return send_csv('labotel_stats.csv', headers, rows)
