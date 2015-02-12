from __future__ import unicode_literals

from indico.core.notifications import email_sender
from indico.modules.events.requests.notifications import notify_request_managers


@email_sender
def notify_relocated_request(req):
    """Notifies request managers about a location change"""
    return notify_request_managers(req, 'relocated_to_request_managers.txt')


@email_sender
def notify_rescheduled_request(req):
    """Notifies request managers about a date/time change"""
    return notify_request_managers(req, 'rescheduled_to_request_managers.txt')
