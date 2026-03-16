# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import datetime

from celery.schedules import crontab

from indico.core.celery import celery
from indico.core.db import db

from .codimd import _archive_codimd_content


# run task at 1AM
@celery.periodic_task(run_every=crontab(hour=1), plugin='conversion')
def archive_codimd_content(
    *,
    start_dt: datetime | None = None,
    exclude_category_ids: list[int] | None = None,
):
    from indico_conversion.plugin import ConversionPlugin

    if ConversionPlugin.settings.get('maintenance'):
        ConversionPlugin.logger.warning('Plugin is in maintenance mode')

    _archive_codimd_content(start_dt, exclude_category_ids)
    db.session.commit()
