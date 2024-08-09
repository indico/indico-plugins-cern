# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from functools import partial

from flask_pluginengine import depends, render_plugin_template
from wtforms.fields import BooleanField, IntegerField, URLField
from wtforms.validators import DataRequired, NumberRange
from wtforms_sqlalchemy.fields import QuerySelectField

from indico.core.config import config
from indico.core.plugins import IndicoPlugin, PluginCategory
from indico.core.settings.converters import ModelConverter
from indico.modules.events.views import WPConferenceDisplay, WPSimpleEventDisplay
from indico.modules.rb.models.room_features import RoomFeature
from indico.modules.vc.views import WPVCEventPage, WPVCManageEvent
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from indico.web.forms.widgets import SwitchWidget

from indico_ravem import _


class SettingsForm(IndicoForm):  # pragma: no cover
    debug = BooleanField(_('Debug mode'), widget=SwitchWidget(),
                         description=_('If enabled, no actual connect/disconnect requests are sent'))
    api_endpoint = URLField(_('API endpoint'), [DataRequired()], filters=[lambda x: x.rstrip('/') + '/'],
                            description=_('The endpoint for the RAVEM API'))
    access_token = IndicoPasswordField(_('Access token'), [DataRequired()], toggle=True,
                                       description=_('The access token used to connect to the RAVEM API'))
    timeout = IntegerField(_('Timeout'), [NumberRange(min=0)],
                           description=_('The amount of time in seconds to wait for RAVEM to reply<br>'
                                         '(0 to disable the timeout)'))
    polling_limit = IntegerField(_('Polling limit'), [NumberRange(min=1)],
                                 description=_('The maximum number of time Indico should poll RAVEM for the status of '
                                               'an operation before considering it as failed<br>'
                                               '(delete the cached var.js to take effect)'))
    polling_interval = IntegerField(_('Polling interval'), [NumberRange(min=1000)],
                                    description=_('The delay between two polls in ms, at least 1000 ms<br>'
                                                  '(delete the cached var.js to take effect)'))
    room_feature = QuerySelectField(_('Room feature'), [DataRequired()], allow_blank=True,
                                    query_factory=lambda: RoomFeature.query, get_label='title',
                                    description=_('The room equipment feature for videoconference capable rooms'))


@depends('vc_zoom')
class RavemPlugin(IndicoPlugin):
    """RAVEM

    Manages connections from physical rooms to videoconference rooms through Indico using
    the RAVEM API.
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'debug': False,
        'api_endpoint': '',
        'access_token': None,
        'timeout': 30,
        'polling_limit': 8,
        'polling_interval': 4000,
        'room_feature': None
    }
    settings_converters = {
        'room_feature': ModelConverter(RoomFeature),
    }
    category = PluginCategory.videoconference

    def init(self):
        super().init()
        if not config.ENABLE_ROOMBOOKING and 'INDICO_DUMPING_URLS' not in os.environ:
            from indico_ravem.util import RavemException
            raise RavemException('RoomBooking is inactive.')

        self.template_hook('manage-event-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button.html'))
        self.template_hook('event-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button.html'))
        self.template_hook('event-timetable-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button.html'))

        self.inject_bundle('main.js', WPSimpleEventDisplay)
        self.inject_bundle('main.js', WPVCEventPage)
        self.inject_bundle('main.js', WPVCManageEvent)
        self.inject_bundle('main.js', WPConferenceDisplay)

    def get_blueprints(self):
        from indico_ravem.blueprint import blueprint
        return blueprint

    def get_vars_js(self):  # pragma: no cover
        return {'polling': {'limit': self.settings.get('polling_limit'),
                            'interval': self.settings.get('polling_interval')}}

    def inject_connect_button(self, template, event_vc_room, **kwargs):  # pragma: no cover
        from indico_ravem.util import has_access
        if event_vc_room.vc_room.type not in ('vidyo', 'zoom') or not has_access(event_vc_room):
            return

        return render_plugin_template(template, room_name=event_vc_room.link_object.room.name,
                                      event_vc_room=event_vc_room, **kwargs)
