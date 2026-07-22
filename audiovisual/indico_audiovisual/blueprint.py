# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_audiovisual.api import RHCreateLink
from indico_audiovisual.controllers import RHRequestCalendar, RHRequestCalendarLink, RHRequestList


blueprint = IndicoPluginBlueprint('audiovisual', __name__, url_prefix='/service/audiovisual')
blueprint.add_url_rule('/', 'request_list', RHRequestList)
blueprint.add_url_rule('/calendar.ics', 'request_calendar', RHRequestCalendar)
blueprint.add_url_rule('/calendar-link', 'request_calendar_link', RHRequestCalendarLink, methods=('GET', 'POST'))
blueprint.add_url_rule('!/api/audiovisual/create-link', 'api_create_link', RHCreateLink, methods=('POST',))
