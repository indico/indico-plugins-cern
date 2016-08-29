from __future__ import unicode_literals

from functools import partial

from flask_pluginengine import depends, render_plugin_template
from wtforms.fields import IntegerField
from wtforms.fields.simple import StringField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired, NumberRange

from indico.core.config import Config
from indico.core.plugins import IndicoPlugin, PluginCategory
from indico.modules.vc.views import WPVCEventPage, WPVCManageEvent
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField
from MaKaC.webinterface.pages.conferences import WPTPLConferenceDisplay

from indico_ravem import _


class SettingsForm(IndicoForm):  # pragma: no cover
    api_endpoint = URLField(_('API endpoint'), [DataRequired()], filters=[lambda x: x.rstrip('/') + '/'],
                            description=_('The endpoint for the RAVEM API'))
    username = StringField(_('Username'), [DataRequired()],
                           description=_('The username used to connect to the RAVEM API'))
    password = IndicoPasswordField(_('Password'), [DataRequired()], toggle=True,
                                   description=_('The password used to connect to the RAVEM API'))
    prefix = IntegerField(_('Room IP prefix'), [NumberRange(min=0)],
                          description=_('IP prefix to connect a room to a Vidyo room.'))
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


@depends('vc_vidyo')
class RavemPlugin(IndicoPlugin):
    """RAVEM

    Manages connections from physical rooms to Vidyo rooms through Indico using
    the RAVEM API.
    """
    configurable = True
    strict_settings = True
    settings_form = SettingsForm
    default_settings = {
        'api_endpoint': 'https://ravem.cern.ch/api/services',
        'username': 'ravem',
        'password': None,
        'prefix': 21,
        'timeout': 10,
        'polling_limit': 8,
        'polling_interval': 4000
    }
    category = PluginCategory.videoconference

    def init(self):
        super(RavemPlugin, self).init()
        if not Config.getInstance().getIsRoomBookingActive():
            from indico_ravem.util import RavemException
            raise RavemException('RoomBooking is inactive.')

        self.template_hook('manage-event-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button.html'))
        self.template_hook('event-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button_group.html'))
        self.template_hook('event-timetable-vc-extra-buttons',
                           partial(self.inject_connect_button, 'ravem_button_group.html'))

        self.inject_js('ravem_js', WPTPLConferenceDisplay)
        self.inject_js('ravem_js', WPVCEventPage)
        self.inject_js('ravem_js', WPVCManageEvent)

    def get_blueprints(self):
        from indico_ravem.blueprint import blueprint
        return blueprint

    def register_assets(self):
        self.register_js_bundle('ravem_js', 'js/ravem.js')

    def get_vars_js(self):  # pragma: no cover
        return {'polling': {'limit': self.settings.get('polling_limit'),
                            'interval': self.settings.get('polling_interval')}}

    def inject_connect_button(self, template, event_vc_room, **kwargs):  # pragma: no cover
        from indico_ravem.util import has_access
        if event_vc_room.vc_room.type != 'vidyo' or not has_access(event_vc_room):
            return

        return render_plugin_template(template, room_name=event_vc_room.link_object.room.name,
                                      event_vc_room=event_vc_room, **kwargs)
