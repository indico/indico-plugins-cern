from __future__ import unicode_literals

from flask_pluginengine import current_plugin
from sqlalchemy.orm.attributes import flag_modified

from indico.modules.events.requests import RequestDefinitionBase
from indico.modules.events.requests.models.requests import RequestState
from indico.util.i18n import _

from indico_requests_audiovisual import util
from indico_requests_audiovisual.forms import AVRequestForm
from indico_requests_audiovisual.util import is_av_manager, send_webcast_ping, get_data_identifiers


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
        super(AVRequest, cls).send(req, data)
        req.data['identifiers'] = get_data_identifiers(req)
        flag_modified(req, 'data')

    @classmethod
    def withdraw(cls, req, notify_event_managers=True):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).withdraw(req, notify_event_managers)

    @classmethod
    def accept(cls, req, data, user):
        if 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).accept(req, data, user)

    @classmethod
    def reject(cls, req, data, user):
        if req.state == RequestState.accepted and 'webcast' in req.data['services']:
            send_webcast_ping()
        super(AVRequest, cls).reject(req, data, user)
