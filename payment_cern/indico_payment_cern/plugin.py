from __future__ import unicode_literals

from wtforms.fields.core import StringField, BooleanField
from wtforms.fields.html5 import URLField, EmailField
from wtforms.validators import DataRequired

from indico.core.plugins import IndicoPlugin
from indico.modules.payment import PaymentPluginMixin, PaymentPluginSettingsFormBase, PaymentEventSettingsFormBase
from indico.util.i18n import _


class PluginSettingsForm(PaymentPluginSettingsFormBase):
    fp_email_address = EmailField(_('FP email adress'), [DataRequired()], description=_('Email address to contact FP.'))
    fp_department_name = StringField(_('FP department name'), [DataRequired()])
    payment_url = URLField(_('Payment URL'), [DataRequired()], description=_('URL used for the epayment'))
    shop_id = StringField(_('Shop ID'), [DataRequired()])
    master_shop_id = StringField(_('Master shop ID'), [DataRequired()])
    hash_seed = StringField(_('Hash seed'), [DataRequired()])
    hash_seed_out = StringField(_('Hash seed out'), [DataRequired()])
    server_url_suffix = StringField(_('Server URL Suffix'), [DataRequired()],
                                    description='Server URL Suffix (indico[suffix].cern.ch)')
    order_id_prefix = StringField(_('Order ID Prefix'), [DataRequired()])
    # TODO: Add payment methods


class EventSettingsForm(PaymentEventSettingsFormBase):
    apply_fees = BooleanField(_('Apply fees'))
    # TODO: Add payment methods


class CERNPaymentPlugin(PaymentPluginMixin, IndicoPlugin):
    """Payment: CERN YellowPay"""
    settings_form = PluginSettingsForm
    event_settings_form = EventSettingsForm
    default_settings = {'method_name': 'CERN YellowPay'}
