# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import date

from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db
from indico.core.notifications import make_email, send_email
from indico.core.plugins import get_plugin_template_module
from indico.modules.rb.models.reservation_occurrences import ReservationOccurrence
from indico.modules.rb.models.reservations import Reservation

from indico_startup_assistance.plugin import StartupAssistanceRequestPlugin


def _send_email(recipients, template):
    email = make_email(from_address='noreply-indico-team@cern.ch', to_list=recipients, template=template, html=True)
    send_email(email)


def _get_reservations():
    return (Reservation.query
            .filter(db.cast(Reservation.start_dt, db.Date) == date.today(),
                    ReservationOccurrence.is_valid,
                    Reservation.is_accepted,
                    Reservation.needs_assistance)
            .join(ReservationOccurrence)
            .order_by(Reservation.start_dt)
            .all())


@celery.periodic_task(run_every=crontab(minute='0', hour='6'), plugin='startup_assistance')
def startup_assistance_emails():
    reservations = _get_reservations()
    reservations_by_room = OrderedDict()
    for reservation in reservations:
        if reservation.room in reservations_by_room:
            reservations_by_room[reservation.room].append(reservation)
        else:
            reservations_by_room[reservation.room] = [reservation]
    template = get_plugin_template_module('startup_assistance_emails.html', reservations_by_room=reservations_by_room)
    recipients = StartupAssistanceRequestPlugin.settings.get('startup_assistance_recipients')
    if recipients:
        _send_email(recipients, template)
