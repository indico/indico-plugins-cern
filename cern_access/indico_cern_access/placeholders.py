# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from markupsafe import Markup

from indico.core.plugins import url_for_plugin
from indico.modules.designer.placeholders import DesignerPlaceholder
from indico.util.date_time import format_datetime
from indico.util.i18n import _
from indico.util.placeholders import ParametrizedPlaceholder, Placeholder
from indico.web.flask.templating import get_template_module

from indico_cern_access.util import get_access_dates, get_last_request


class TicketAccessDatesPlaceholder(DesignerPlaceholder):
    group = 'event'
    name = 'cern_access_dates'
    description = _('CERN Badges - Access Dates')
    admin_only = True

    @classmethod
    def render(cls, event):
        start_dt, end_dt = get_access_dates(get_last_request(event))
        if start_dt.date() == end_dt.date():
            return format_datetime(start_dt, format='d MMM YYY', locale='en_GB')
        else:
            return '{} - {}'.format(format_datetime(start_dt, format='d MMM YYY', locale='en_GB'),
                                    format_datetime(end_dt, format='d MMM YYY', locale='en_GB'))


class TicketLicensePlatePlaceholder(DesignerPlaceholder):
    group = 'registrant'
    name = 'cern_access_plate'
    description = _('CERN Badges - License Plate')
    admin_only = True

    @classmethod
    def render(cls, registration):
        return registration.cern_access_request.license_plate or ''


class FormLinkPlaceholder(ParametrizedPlaceholder):
    name = 'form_link'
    required = True
    param_required = True
    param_friendly_name = 'link text'
    description = _('Link to the personal data form')

    @classmethod
    def render(cls, param, regform, registration):
        url = url_for_plugin('cern_access.access_identity_data', registration.locator.uuid, _external=True)
        return Markup(f'<a href="{url}">{param}</a>')


class AccessPeriodPlaceholder(ParametrizedPlaceholder):
    name = 'access_period'
    param_required = True
    param_restricted = True
    param_friendly_name = 'locale'
    description = None

    @classmethod
    def iter_param_info(cls, regform, registration):
        yield 'en', _('Period where site access will be granted (english date format)')
        yield 'fr', _('Period where site access will be granted (french date format)')

    @classmethod
    def render(cls, param, regform, registration):
        locale_data = {
            'en': {'locale': 'en_GB', 'separator': 'to'},
            'fr': {'locale': 'fr_FR', 'separator': 'au'},
        }
        start_dt, end_dt = get_access_dates(get_last_request(registration.event))
        tpl = get_template_module('cern_access:_common.html')
        return Markup(tpl.render_access_dates(start_dt, end_dt, **locale_data[param]))


class AccessCodePlaceholder(Placeholder):
    name = 'cern_access_code'
    description = _('The access code to print a CERN visitor badge')

    @classmethod
    def render(cls, regform, registration):
        if not (req := registration.cern_access_request):
            return '-------'
        if not req.is_active or not req.has_identity_info:
            return '-------'
        return req.reservation_code
