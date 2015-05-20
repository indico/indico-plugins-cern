from __future__ import unicode_literals

from celery.schedules import crontab

from indico.core.celery import celery
from indico.util.i18n import make_bound_gettext


_ = make_bound_gettext('outlook')


@celery.periodic_task(run_every=crontab(minute='*/15'))
def scheduled_update():
    from indico_outlook.calendar import update_calendar
    update_calendar()
