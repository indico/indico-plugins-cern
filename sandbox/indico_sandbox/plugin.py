# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import has_request_context, session

from indico.core import signals
from indico.core.config import config
from indico.core.notifications import make_email
from indico.core.plugins import IndicoPlugin
from indico.util.signals import interceptable_sender


class SandboxPlugin(IndicoPlugin):
    """Sandbox

    Provides utilities for the sandbox instance.
    """

    def init(self):
        super().init()
        self.connect(signals.event.reminder.before_reminder_make_email, self._before_reminder_make_email)
        self.connect(signals.plugin.interceptable_function, self._intercept_make_email,
                     sender=interceptable_sender(make_email))

    def _before_reminder_make_email(self, reminder, to_list, **kwargs):
        return {'to_list': reminder.creator.email}

    def _intercept_make_email(self, sender, func, args, **kwargs):
        ret = func(**args.arguments)

        if not has_request_context():
            # If we're outside the request context (i.e. in a celery task),
            # we can't access the session so we just return the original email unmodified.
            # This can happen for data export and event reminders (and maybe some other places?).
            # Event reminders are handled separately by overwriting their recipient list, since we
            # do not have a session user when a scheduled reminder is sent.
            return ret

        if session.get('register_verification_email_sent'):
            # Let verification emails through
            return ret

        # If the user is logged in, redirect the email to them, otherwise do not send it
        # (If 'to', 'cc' and 'bcc' are all empty, djangomail won't send the email)
        to = {session.user.email} if session.user else set()
        overrides = {
            'to': to,
            'cc': set(),
            'bcc': set(),
            'from': config.NO_REPLY_EMAIL,
            'reply_to': set(),
            'attachments': ret['attachments'],
            'subject': ret['subject'],
            'body': ret['body'],
            'html': ret['html'],
        }
        return ret | overrides
