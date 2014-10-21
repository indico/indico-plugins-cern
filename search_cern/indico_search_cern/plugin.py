from __future__ import unicode_literals

from wtforms.fields.html5 import URLField
from wtforms.validators import URL

from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico_search import SearchPluginBase

from indico_search_cern.blueprint import blueprint


class SettingsForm(IndicoForm):
    search_url = URLField(_('CERNsearch URL'), [URL()])


class CERNSearchPlugin(SearchPluginBase):
    """CERN Search

    Uses CERNsearch as Indico's search engine
    """

    settings_form = SettingsForm
    default_settings = {
        'search_url': 'https://search.cern.ch/Pages/IndicoFrame.aspx'
    }

    def get_blueprints(self):
        return blueprint
