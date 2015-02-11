from __future__ import unicode_literals

from flask_pluginengine import current_plugin

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState
from indico.util.i18n import _

from indico_requests_audiovisual import util
from indico_requests_audiovisual.forms import AVRequestForm
from indico_requests_audiovisual.util import is_av_manager, send_webcast_ping


class AVRequest(RequestDefinitionBase):
    name = 'webcast-recording'
    title = _('Webcast / Recording')
    form = AVRequestForm
    form_defaults = {'all_contributions': True}
    util = util  # needed for templates where we only have access to the definition

    @classmethod
    def can_be_managed(cls, user):
        return user.isAdmin() or is_av_manager(user)

    @classmethod
    def get_manager_notification_emails(cls):
        return set(current_plugin.settings.get('notification_emails'))

    @classmethod
    def send(cls, req, data):
        if (req.id is not None and req.state == RequestState.accepted and
                ('webcast' in req.data['services']) != ('webcast' in data['services'])):
            send_webcast_ping()
        return super(AVRequest, cls).send(req, data)

    @classmethod
    def accept(cls, req, data, user):
        if 'webcast' in req.data['services']:
            send_webcast_ping()
        return super(AVRequest, cls).accept(req, data, user)

    @classmethod
    def reject(cls, req, data, user):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping()
        return super(AVRequest, cls).reject(req, data, user)
