from __future__ import unicode_literals

from wtforms.fields.core import SelectField, BooleanField, FloatField
from wtforms.fields.html5 import URLField, IntegerField
from wtforms.fields.simple import TextField
from wtforms.validators import DataRequired, NumberRange

from indico.core.plugins import IndicoPlugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import UnsafePasswordField


_status_choices = [('free', _('Free')),
                   ('busy', _('Busy')),
                   ('tentative', _('Tentative')),
                   ('oof', _('Out of office'))]


class SettingsForm(IndicoForm):
    service_url = URLField(_('Service URL'), description=_("The URL of the CERN calendar service"))
    username = TextField(_('Username'), [DataRequired()],
                         description=_("The username used to authenticate with the CERN calendar service"))
    password = UnsafePasswordField(_('Password'), [DataRequired()],
                                   description=_("The password used to authenticate with the CERN calendar service"))
    status = SelectField(_('Status'), [DataRequired()], choices=_status_choices,
                         description=_("The default status of the event in the calendar"))
    reminder = BooleanField(_('Reminder'), description=_("Enable calendar reminder"))
    reminder_minutes = IntegerField(_('Reminder time'), [NumberRange(min=0)],
                                    description=_("Remind users X minutes before the event"))
    operation_prefix = TextField(_('Prefix'), [DataRequired()],
                                 description=_("Prefix for calendar item IDs. If you change this, existing calendar "
                                               "entries cannot be deleted/updated anymore!"))
    timeout = FloatField(_('Request timeout'), [NumberRange(min=0.25)], description=_("Request timeout in seconds"))


class OutlookPlugin(IndicoPlugin):
    """Outlook Integration

    Enables outlook calendar notifications when a user registers in a conference or participates in a meeting/lecture.
    """

    settings_form = SettingsForm
    default_settings = {
        'status': 'free',
        'reminder': True,
        'reminder_minutes': 15,
        'prefix': 'indico_',
        'timeout': 3
    }
