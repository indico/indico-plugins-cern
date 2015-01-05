from __future__ import unicode_literals

from wtforms.fields.core import StringField, BooleanField
from wtforms.fields.html5 import URLField, EmailField
from wtforms.validators import DataRequired

from indico.core.plugins import IndicoPlugin
from indico.modules.payment import PaymentPluginMixin, PaymentPluginSettingsFormBase, PaymentEventSettingsFormBase
from indico.util.i18n import _
from indico.util.user import retrieve_principals
from indico.web.forms.fields import PrincipalField


class PluginSettingsForm(PaymentPluginSettingsFormBase):
    authorized_users = PrincipalField(_('Authorized users'), groups=True,
                                      description=_('List of users/groups who are authorized to configure the CERN '
                                                    'Payment module for any event.'))
    fp_email_address = EmailField(_('FP email adress'), [DataRequired()], description=_('Email address to contact FP.'))
    fp_department_name = StringField(_('FP department name'), [DataRequired()])
    payment_url = URLField(_('Payment URL'), [DataRequired()], description=_('URL used for the epayment'))
    shop_id = StringField(_('Shop ID'), [DataRequired()])
    master_shop_id = StringField(_('Master shop ID'), [DataRequired()])
    hash_seed = StringField(_('Hash seed'), [DataRequired()])
    hash_seed_out = StringField(_('Hash seed out'), [DataRequired()])
    server_url_suffix = StringField(_('Server URL Suffix'), description='Server URL Suffix (indico[suffix].cern.ch)')
    order_id_prefix = StringField(_('Order ID Prefix'))
    # TODO: Add payment methods


class EventSettingsForm(PaymentEventSettingsFormBase):
    apply_fees = BooleanField(_('Apply fees'))
    # TODO: Add payment methods


class CERNPaymentPlugin(PaymentPluginMixin, IndicoPlugin):
    """Payment: CERN YellowPay"""
    settings_form = PluginSettingsForm
    event_settings_form = EventSettingsForm
    default_settings = {'method_name': 'CERN YellowPay'}
    valid_currencies = {'CHF'}

    def can_be_modified(self, user, event):
        if user.isAdmin():
            return True
        authorized_users = retrieve_principals(self.settings.get('authorized_users'))
        return any(principal.containsUser(user) for principal in authorized_users)
