from __future__ import unicode_literals

from collections import OrderedDict
from datetime import datetime, timedelta

from celery.schedules import crontab
from sqlalchemy import cast, Date, Time

from indico.core.celery import celery
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.modules.events.models.events import Event
from indico.modules.rb.models.reservations import Reservation
from indico.util.date_time import as_utc, format_date
from indico.util.string import to_unicode

from indico_cronjobs_cern.plugin import CERNCronjobsPlugin


def _get_start_end_dt():
    start_dt = as_utc(datetime.today() + timedelta(days=(7 - int(datetime.today().strftime('%w')))))
    end_dt = as_utc(start_dt + timedelta(days=14))
    return start_dt, end_dt


def _group_by_date(object_list):
    objects_grouped_by_date = OrderedDict()
    for obj in object_list:
        date = to_unicode(format_date(obj.start_dt, format='full'))
        if date in objects_grouped_by_date:
            objects_grouped_by_date[date].append(obj)
        else:
            objects_grouped_by_date[date] = [obj]
    return objects_grouped_by_date


def _get_reservations_query(start_dt, end_dt, room_id=None):
    filters = [
        ~Reservation.is_cancelled,
        ~Reservation.is_rejected,
        Reservation.needs_assistance,
        cast(Reservation.start_dt, Date) <= end_dt.date(),
        cast(Reservation.end_dt, Date) >= start_dt.date()
    ]
    if room_id:
        filters.append(Reservation.room_id == room_id)

    return Reservation.query.filter(*filters).order_by(Reservation.start_dt)


def _get_category_events_query(start_dt, end_dt, category_ids):
    return (Event.query
            .filter(~Event.is_deleted,
                    Event.category_chain_overlaps(category_ids),
                    Event.happens_between(start_dt, end_dt))
            .order_by(Event.start_dt))


def _send_email(recipients, template):
    email = make_email(from_address='noreply-indico-team@cern.ch', to_list=recipients, template=template, html=True)
    send_email(email, module='Indico Cronjobs CERN')


@celery.periodic_task(run_every=crontab(minute='0', hour='8', day_of_week='friday'), plugin='cronjobs_cern')
def conference_room_emails():
    start_dt, end_dt = _get_start_end_dt()
    globe_room_id = 175
    events_by_room = {}
    for room in CERNCronjobsPlugin.settings.get('rooms'):
        query = (Event.query
                 .filter(~Event.is_deleted,
                         Event.happens_between(start_dt, end_dt),
                         Event.own_room_id == room.id)
                 .order_by(Event.start_dt))
        events_by_room[room] = _group_by_date(query)

    reservations = _get_reservations_query(start_dt, end_dt, room_id=globe_room_id)

    category_ids = [int(category['id']) for category in CERNCronjobsPlugin.settings.get('categories')]
    committees = _get_category_events_query(start_dt, end_dt, category_ids)

    template = get_plugin_template_module('conference_room_email.html',
                                          events_by_room=events_by_room,
                                          reservations_by_date=_group_by_date(reservations),
                                          committees_by_date=_group_by_date(committees))
    recipients = CERNCronjobsPlugin.settings.get('conf_room_recipients')
    if recipients:
        _send_email(recipients, template)
