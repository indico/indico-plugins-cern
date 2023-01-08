# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.notifications import email_sender, make_email
from indico.web.flask.templating import get_template_module


@email_sender
def notify_automatic_cancellation(booking):
    booked_for_user = booking.booked_for_user
    tpl = get_template_module('burotel:emails/automatic_cancellation.html',
                              booking=booking, user=booked_for_user)
    cc_list = {booking.created_by_user.email} if booking.created_by_user != booked_for_user else None
    return make_email(to_list={booked_for_user.email}, cc_list=cc_list, template=tpl, html=True)


@email_sender
def notify_about_to_cancel(booking):
    booked_for_user = booking.booked_for_user
    tpl = get_template_module('burotel:emails/about_to_cancel.html',
                              booking=booking, user=booking.booked_for_user)
    cc_list = {booking.created_by_user.email} if booking.created_by_user != booked_for_user else None
    return make_email(to_list={booked_for_user.email}, cc_list=cc_list, template=tpl, html=True)
