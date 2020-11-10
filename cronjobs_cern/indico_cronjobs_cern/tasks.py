# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import date, datetime, time, timedelta

from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.modules.events.models.events import Event
from indico.util.date_time import as_utc, format_date

from indico_cronjobs_cern.plugin import CERNCronjobsPlugin


def _get_start_end_date():
    today = date.today()
    start_date = today + timedelta(days=(7 - int(today.strftime('%w'))))
    end_date = start_date + timedelta(days=14)
    return start_date, end_date


def _group_by_date(object_list):
    objects_grouped_by_date = OrderedDict()
    for obj in object_list:
        date = format_date(obj.start_dt, format='full')
        if date in objects_grouped_by_date:
            objects_grouped_by_date[date].append(obj)
        else:
            objects_grouped_by_date[date] = [obj]
    return objects_grouped_by_date


def _get_category_events_query(start_dt, end_dt, category_ids):
    return (Event.query
            .filter(~Event.is_deleted,
                    Event.category_chain_overlaps(category_ids),
                    Event.happens_between(start_dt, end_dt))
            .order_by(Event.start_dt))


def _send_email(recipients, template):
    email = make_email(from_address='noreply-indico-team@cern.ch', to_list=recipients, template=template, html=True)
    send_email(email, module='Indico Cronjobs CERN')


@celery.periodic_task(run_every=crontab(minute='0', hour='8', day_of_week='monday'), plugin='cronjobs_cern')
def seminar_emails():
    start_date, end_date = _get_start_end_date()
    start_dt = as_utc(datetime.combine(start_date, time()))
    end_dt = as_utc(datetime.combine(end_date, time()))
    seminar_categories = CERNCronjobsPlugin.settings.get('seminar_categories')
    if not seminar_categories:
        return
    category_ids = [int(category['id']) for category in seminar_categories]
    query = _get_category_events_query(start_dt, end_dt, category_ids)
    template = get_plugin_template_module('seminar_emails.html', events_by_date=_group_by_date(query))
    recipients = CERNCronjobsPlugin.settings.get('seminar_recipients')
    if recipients:
        _send_email(recipients, template)
