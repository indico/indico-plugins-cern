from __future__ import unicode_literals
from wtforms.fields.core import SelectField

from wtforms.fields.html5 import URLField
from wtforms.validators import URL

from indico.core.plugins import IndicoPluginBlueprint
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico_search import SearchPluginBase

from indico_search_cern.engine import CERNSearchEngine


class SettingsForm(IndicoForm):
    search_url = URLField(_('CERNsearch URL'), [URL()])
    display_mode = SelectField(_('Display mode'), choices=[('iframe', _('Embedded (IFrame)')),
                                                           ('redirect', _('External (Redirect)'))])


class CERNSearchPlugin(SearchPluginBase):
    """CERN Search

    Uses CERNsearch as Indico's search engine
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'search_url': 'https://search.cern.ch/Pages/IndicoFrame.aspx',
        'display_mode': 'iframe'
    }
    engine_class = CERNSearchEngine

    def get_blueprints(self):
        return IndicoPluginBlueprint('search_cern', 'indico_search_cern')
