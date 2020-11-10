# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.


from celery.schedules import crontab

from indico.core.celery import celery
from indico.util.i18n import make_bound_gettext


_ = make_bound_gettext('outlook')


@celery.periodic_task(run_every=crontab(minute='*/15'))
def scheduled_update():
    from indico_outlook.calendar import update_calendar
    update_calendar()
