# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_vc_assistance.controllers import RHRequestCalendar, RHRequestCalendarLink, RHRequestList


blueprint = IndicoPluginBlueprint('vc_assistance', __name__, url_prefix='/service/vc-assistance')
blueprint.add_url_rule('/', 'request_list', RHRequestList)
blueprint.add_url_rule('/calendar.ics', 'request_calendar', RHRequestCalendar)
blueprint.add_url_rule('/calendar-link', 'request_calendar_link', RHRequestCalendarLink, methods=('GET', 'POST'))
