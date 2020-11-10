# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db
from indico.util.i18n import make_bound_gettext


_ = make_bound_gettext('cern_access')


@celery.periodic_task(run_every=crontab(minute='0', hour='5'))
def scheduled_sanitization():
    from indico_cern_access.util import sanitize_personal_data
    sanitize_personal_data()
    db.session.commit()
