from __future__ import unicode_literals

from indico.core.plugins import IndicoPlugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import PrincipalField, MultipleItemsField


class PluginSettingsForm(IndicoForm):
    managers = PrincipalField(_('Managers'), groups=True,
                              description=_('List of users who can manage recording/webcast requests.'))
    webcast_audiences = MultipleItemsField(_('Webcast Audiences'), fields=[('audience', _('Audience'))],
                                           unique_field='audience',
                                           description=_('List of audiences for non-public webcasts.'))
    # TODO: notification settings
    # TODO: ping url when request is accepted
    # TODO: agreement settings


class AVRequestsPlugin(IndicoPlugin):
    """Webcast & Recording Request

    Provides a service request where event managers can ask for their
    event to be recorded or webcast.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {'managers': [],
                        'webcast_audiences': []}
    strict_settings = True

    def init(self):
        super(AVRequestsPlugin, self).init()
        # TODO: remove method or add some code
