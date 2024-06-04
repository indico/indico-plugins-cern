# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import has_request_context, session
from flask_pluginengine.plugin import render_plugin_template
from wtforms.fields import IntegerField
from wtforms.validators import NumberRange, Optional

from indico.core import signals
from indico.core.config import config
from indico.core.notifications import make_email
from indico.core.plugins import IndicoPlugin
from indico.modules.categories.models.categories import Category
from indico.util.signals import interceptable_sender
from indico.web.forms.base import IndicoForm

from indico_i18n_demo.blueprint import blueprint


class PluginSettingsForm(IndicoForm):
    test_category_id = IntegerField('Test category ID', [Optional(), NumberRange(min=1)],
                                    description='The ID of the category to clone events to')


class I18nDemoPlugin(IndicoPlugin):
    """I18n Demo

    Provides utilities for the i18n-demo instance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {
        'test_category_id': ''
    }

    def init(self):
        super().init()
        self.template_hook('event-status-labels', self._inject_clone_button)
        self.connect(signals.plugin.interceptable_function, self._intercept_make_email,
                     sender=interceptable_sender(make_email))

    def get_blueprints(self):
        return blueprint

    def _inject_clone_button(self, event, **kwargs):
        if not (test_category_id := self.settings.get('test_category_id')):
            return

        if not (test_category := Category.get(int(test_category_id))):
            return

        if event.category != test_category and not event.category.is_descendant_of(test_category):
            return render_plugin_template('clone_button.html', event=event)

    def _intercept_make_email(self, sender, func, args, **kwargs):
        ret = func(**args.arguments)

        if not has_request_context():
            # If we're outside the request context (i.e. in a celery task),
            # we can't access the session so we just return the original email unmodified.
            # This can happen for data export and event reminders (and maybe some other places?).
            # In those cases, we trust the users not to spam random people.
            return ret

        overrides = {
            'to': session.user.email,
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
