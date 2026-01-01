# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os

from flask import current_app, redirect, request, url_for

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.rb.models.rooms import Room
from indico.modules.rb.schemas import RoomSchema
from indico.web.flask.util import make_view_func

from indico_labotel.blueprint import blueprint
from indico_labotel.cli import cli
from indico_labotel.controllers import RHLanding, WPLabotelBase


class LabotelPlugin(IndicoPlugin):
    """Labotel

    Provides labotel-specific functionality
    """

    def init(self):
        super().init()
        current_app.before_request(self._before_request)
        self.connect(signals.plugin.cli, self._extend_indico_cli)
        self.connect(signals.plugin.get_template_customization_paths, self._override_templates)
        self.connect(signals.plugin.schema_post_dump, self._inject_prompt_attribute, sender=RoomSchema)
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

    def _inject_prompt_attribute(self, sender, data, **kwargs):
        prompts = {room.id: value for room, value in Room.find_with_attribute('confirmation-prompt') if value}
        for room in data:
            room['confirmation_prompt'] = prompts.get(room['id'])
