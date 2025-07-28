# This file is part of the CERN Indico plugins.
# Copyright (C) 2024 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField, FloatField, URLField
from wtforms.validators import URL, DataRequired, NumberRange

from indico.core import signals
from indico.core.plugins import IndicoPlugin, PluginCategory
from indico.modules.events.contributions.models.contributions import Contribution
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.vc.models.vc_rooms import VCRoomEventAssociation
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico.web.forms.widgets import SwitchWidget

from indico_zoom_rooms import _, handlers
from indico_zoom_rooms.util import get_zoom_room_id


class PluginSettingsForm(IndicoForm):
    debug = BooleanField(
        _('Debug mode'),
        widget=SwitchWidget(),
        description=_('If enabled, requests are not sent to the API but logged instead'),
    )
    service_url = URLField(
        _('Service URL'), [URL(require_tld=False)], description=_('The URL of the CERN calendar service')
    )
    docs_url = URLField(
        _('Documentation URL'), [DataRequired(), URL()], description=_('The URL the "Zoom Rooms" buttons will link to')
    )
    token = IndicoPasswordField(
        _('Token'),
        [DataRequired()],
        toggle=True,
        description=_('The token used to authenticate with the CERN calendar service'),
    )
    timeout = FloatField(_('Request timeout'), [NumberRange(min=0.25)], description=_('Request timeout in seconds'))


class ZoomRoomsPlugin(IndicoPlugin):
    """Zoom Rooms

    Zoom Rooms / Exchange synchronization plugin for Indico.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {'debug': False, 'service_url': None, 'docs_url': '', 'token': None, 'timeout': 3}
    category = PluginCategory.videoconference

    def init(self):
        super().init()
        # Here we plug the various object signals into the action tracking code
        # Consult the README.md for a summary of the logic behind
        self.connect(signals.event.contribution_updated, handlers.signal_link_object_updated)
        self.connect(signals.event.session_block_updated, handlers.signal_link_object_updated)
        self.connect(signals.event.updated, handlers.signal_event_updated)
        self.connect(signals.event.times_changed, handlers.signal_tt_entry_updated, sender=Contribution)
        self.connect(signals.event.times_changed, handlers.signal_tt_entry_updated, sender=SessionBlock)
        self.connect(signals.vc.vc_room_created, handlers.signal_zoom_meeting_created)
        self.connect(signals.vc.vc_room_cloned, handlers.signal_zoom_meeting_cloned)
        self.connect(signals.vc.vc_room_attached, handlers.signal_zoom_meeting_association_attached)
        self.connect(signals.vc.vc_room_detached, handlers.signal_zoom_meeting_association_detached)
        self.connect(signals.vc.vc_room_data_updated, handlers.signal_zoom_meeting_data_updated)

        self.template_hook('manage-event-vc-extra-buttons', self.inject_button)
        self.template_hook('event-vc-extra-buttons', self.inject_button)
        self.template_hook('event-timetable-vc-extra-buttons', self.inject_button)

    def inject_button(self, event_vc_room: VCRoomEventAssociation, **_kwargs: dict):
        if event_vc_room.vc_room.type != 'zoom' or not event_vc_room.link_object.room:
            return

        if zr_id := get_zoom_room_id(event_vc_room.link_object):
            return render_plugin_template(
                'explanation.html',
                room_name=event_vc_room.link_object.room.full_name,
                event_vc_room=event_vc_room,
                zr_id=zr_id,
                docs_url=ZoomRoomsPlugin.settings.get('docs_url'),
            )
