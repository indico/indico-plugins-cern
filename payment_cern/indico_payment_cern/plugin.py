from __future__ import unicode_literals, division

from hashlib import sha512

from flask import request, session
from flask_pluginengine import render_plugin_template
from wtforms.fields.core import StringField, BooleanField
from wtforms.fields.html5 import URLField, EmailField
from wtforms.validators import DataRequired

from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.modules.payment import PaymentPluginMixin, PaymentPluginSettingsFormBase, PaymentEventSettingsFormBase
from indico.modules.payment import event_settings as payment_event_settings
from indico.modules.payment.util import get_registrant_params
from indico.util.i18n import _
from indico.util.string import remove_accents, remove_non_alpha
from indico.util.user import retrieve_principals
from indico.web.flask.util import url_for
from indico.web.forms.fields import PrincipalField, MultipleItemsField, OverrideMultipleItemsField

from indico_payment_cern.blueprint import blueprint
from indico_payment_cern.util import get_payment_methods, get_payment_method, create_hash


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
    shop_id_chf = StringField(_('Shop ID (CHF)'), [DataRequired()])
    shop_id_eur = StringField(_('Shop ID (EUR)'), [DataRequired()])
    hash_seed_chf = StringField(_('Hash seed (CHF)'), [DataRequired()])
    hash_seed_eur = StringField(_('Hash seed (EUR)'), [DataRequired()])
    hash_seed_out_chf = StringField(_('Hash seed out (CHF)'), [DataRequired()])
    hash_seed_out_eur = StringField(_('Hash seed out (EUR)'), [DataRequired()])
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
    """PostFinance CERN

    Providing a payment method using the PostFinance system.
    Extra fees can be set for each payment method so the price after the
    cut taken by the bank is the correct one.
    """
    settings_form = PluginSettingsForm
    event_settings_form = EventSettingsForm
    default_settings = {'method_name': 'PostFinance CERN',
                        'authorized_users': [],
                        'payment_methods': []}
    default_event_settings = {'apply_fees': True,
                              'custom_fees': {}}
    valid_currencies = {'EUR', 'CHF'}

    def init(self):
        super(CERNPaymentPlugin, self).init()
        self.template_hook('event-manage-payment-plugin-cannot-modify', self._get_cannot_modify_message)

    @property
    def logo_url(self):
        return url_for_plugin(self.name + '.static', filename='images/logo.png')

    def get_blueprints(self):
        return blueprint

    def can_be_modified(self, user, event):
        if user.isAdmin():
            return True
        authorized_users = retrieve_principals(self.settings.get('authorized_users'))
        return any(principal.containsUser(user) for principal in authorized_users)

    def _get_cannot_modify_message(self, plugin, event, **kwargs):
        if self != plugin:
            return
        fp_name = self.settings.get('fp_department_name')
        fp_email = self.settings.get('fp_email_address')
        return render_plugin_template('event_settings_readonly.html', fp_name=fp_name, fp_email=fp_email)

    def adjust_payment_form_data(self, data):
        data['postfinance_methods'] = get_payment_methods(data['event'])
        data['selected_method'] = selected_method = request.args.get('postfinance_method', '')
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

        data['form_data'] = self._generate_form_data(data['amount'], data)

    def _get_order_id(self, data):
        registrant = data['registrant']
        prefix = data['settings']['order_id_prefix']
        order_id_extra_len = max(0, 30 - len(registrant.getIdPay()) + len(prefix))
        order_id = prefix + remove_non_alpha(remove_accents(registrant.getSurName() + registrant.getFirstName()))
        return order_id[:order_id_extra_len].upper().strip() + registrant.getIdPay()

    def _generate_form_data(self, amount, data):
        if amount is None:
            return {}

        registrant = data['registrant']
        event = data['event']
        currency = data['currency']
        seed = data['settings']['hash_seed_{}'.format(currency.lower())]
        shop_id = data['settings']['shop_id_{}'.format(currency.lower())]
        method = get_payment_method(event, data['selected_method'])
        template_page = ''  # yes, apparently it's supposed to be empty..
        template_hash = sha512(seed + template_page).hexdigest()
        order_id = self._get_order_id(data)
        parameters = get_registrant_params()

        form_data = {
            'PSPID': shop_id,
            'ORDERID': order_id,
            'AMOUNT': int(amount * 100),
            'CURRENCY': currency,
            'LANGUAGE': session.lang,
            'CN': remove_accents(registrant.getFullName(title=False, firstNameFirst=True)[:35]),
            'EMAIL': registrant.getEmail()[:50],
            'OWNERADDRESS': registrant.getAddress()[:35],
            'OWNERTOWN': registrant.getCity()[:25],
            'OWNERCTY': registrant.getCountry(),
            'OWNERTELNO': registrant.getPhone()[:30],
            'TP': template_page + '&hash=' + template_hash,
            'PM': method['type'],
            'BRAND': method['name'],
            'PARAMVAR': data['settings']['server_url_suffix'],
            'HOMEURL': url_for('event.conferenceDisplay', event, _external=True, _secure=True),
            'ACCEPTURL': url_for_plugin('payment_cern.success', event, _external=True, _secure=True, **parameters),
            'CANCELURL': url_for_plugin('payment_cern.cancel', event, _external=True, _secure=True, **parameters),
            'DECLINEURL': url_for_plugin('payment_cern.decline', event, _external=True, _secure=True, **parameters),
            'EXCEPTIONURL': url_for_plugin('payment_cern.uncertain', event, _external=True, _secure=True, **parameters),
            'BACKURL': url_for('payment.event_payment', event, _external=True, _secure=True, **parameters)
        }
        form_data['SHASIGN'] = create_hash(seed, form_data)
        return form_data
