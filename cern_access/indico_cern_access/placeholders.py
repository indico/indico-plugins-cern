# This file is part of Indico.
# Copyright (C) 2002 - 2017 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from indico.modules.designer.placeholders import DesignerPlaceholder
from indico.util.date_time import format_datetime
from indico.util.i18n import _
from indico.util.string import to_unicode

from indico_cern_access.util import get_access_dates, get_last_request


class AccessDatesPlaceholder(DesignerPlaceholder):
    group = 'event'
    name = 'cern_access_dates'
    description = _("CERN Badges - Access Dates")
    admin_only = True

    @classmethod
    def render(cls, event):
        start_dt, end_dt = get_access_dates(get_last_request(event))
        if start_dt.date() == end_dt.date():
            return to_unicode(format_datetime(start_dt, format='d MMM YYY', locale='en_GB'))
        else:
            return "{} - {}".format(to_unicode(format_datetime(start_dt, format='d MMM YYY', locale='en_GB')),
                                    to_unicode(format_datetime(end_dt, format='d MMM YYY', locale='en_GB')))
