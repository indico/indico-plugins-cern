# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os

from flask import current_app, redirect, request, url_for
from wtforms.fields import SelectField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.auth import multipass
from indico.core.plugins import IndicoPlugin
from indico.web.flask.util import make_view_func
from indico.web.forms.base import IndicoForm

from indico_labotel import _
from indico_labotel.blueprint import blueprint
from indico_labotel.cli import cli
from indico_labotel.controllers import RHLanding, WPLabotelBase


class SettingsForm(IndicoForm):
    cern_identity_provider = SelectField(_('CERN Identity Provider'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cern_identity_provider.choices = [(k, p.title) for k, p in multipass.identity_providers.items()]


class LabotelPlugin(IndicoPlugin):
    """Labotel

    Provides labotel-specific functionality
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'cern_identity_provider': ''
    }
    default_user_settings = {
        'default_experiment': None,
    }

    def init(self):
        super().init()
        current_app.before_request(self._before_request)
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.plugin.get_template_customization_paths, self._override_templates)
        self.inject_bundle('labotel.js', WPLabotelBase)
        self.inject_bundle('labotel.css', WPLabotelBase)

    def get_blueprints(self):
        return blueprint

    def _before_request(self):
        if request.endpoint == 'categories.display':
            return redirect(url_for('rb.roombooking'))
        elif request.endpoint == 'rb.roombooking':
            # render our own landing page instead of the original RH
            return make_view_func(RHLanding)()

    def _extend_indico_cli(self, sender, **kwargs):
        return cli

    def _override_templates(self, sender, **kwargs):
        return os.path.join(self.root_path, 'template_overrides')
