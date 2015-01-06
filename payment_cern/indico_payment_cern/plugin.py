from __future__ import unicode_literals, division

from flask import request
from wtforms.fields.core import StringField, BooleanField
from wtforms.fields.html5 import URLField, EmailField
from wtforms.validators import DataRequired

from indico.core.plugins import IndicoPlugin
from indico.modules.payment import PaymentPluginMixin, PaymentPluginSettingsFormBase, PaymentEventSettingsFormBase
from indico.util.i18n import _
from indico.util.user import retrieve_principals
from indico.web.forms.fields import PrincipalField, MultipleItemsField, OverrideMultipleItemsField

from indico_payment_cern.util import get_payment_methods, get_payment_method


PAYMENT_METHODS_FIELDS = (('name', _("Name")),
                          ('title', _("Displayed Name")),
                          ('type', _("Type")),
                          ('fee', _("Extra Fee (%)")))


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
    payment_methods = MultipleItemsField(_('Payment Methods'), fields=PAYMENT_METHODS_FIELDS, unique_field='name')


class EventSettingsForm(PaymentEventSettingsFormBase):
    apply_fees = BooleanField(_('Apply fees'), description=_('Enables the payment method specific fees.'))
    custom_fees = OverrideMultipleItemsField(_('Payment Methods'), fields=PAYMENT_METHODS_FIELDS, unique_field='name',
                                             edit_fields=['fee'],
                                             description=_('Here the fees of the various payment methods can be '
                                                           'overridden.'))

    def __init__(self, *args, **kwargs):
        super(EventSettingsForm, self).__init__(*args, **kwargs)
        self.custom_fees.field_data = self._plugin_settings['payment_methods']


class CERNPaymentPlugin(PaymentPluginMixin, IndicoPlugin):
    """Payment: CERN YellowPay"""
    settings_form = PluginSettingsForm
    event_settings_form = EventSettingsForm
    default_settings = {'method_name': 'CERN YellowPay',
                        'payment_methods': []}
    default_event_settings = {'apply_fees': True}
    valid_currencies = {'CHF'}

    def can_be_modified(self, user, event):
        if user.isAdmin():
            return True
        authorized_users = retrieve_principals(self.settings.get('authorized_users'))
        return any(principal.containsUser(user) for principal in authorized_users)

    def adjust_payment_form_data(self, data):
        data['yellowpay_methods'] = get_payment_methods(data['event'])
        data['selected_method'] = selected_method = request.args.get('yellowpay_method', '')
        base_amount = data['amount']
        if selected_method:
            method = get_payment_method(data['event'], selected_method)
            modifier = 1 / (1 - method['fee'] / 100)
            data['amount'] = base_amount * modifier
            data['fee'] = data['amount'] - base_amount
        else:
            data['fee'] = None
            if data['event_settings']['apply_fees']:  # we don't know the final price
                data['amount'] = None
