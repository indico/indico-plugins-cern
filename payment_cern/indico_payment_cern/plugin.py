# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re
from decimal import Decimal
from hashlib import sha512

from flask import request, session
from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField, EmailField, StringField, URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.errors import UserValueError
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.modules.events.payment import (PaymentEventSettingsFormBase, PaymentPluginMixin,
                                           PaymentPluginSettingsFormBase)
from indico.util.string import remove_accents, str_to_ascii
from indico.web.flask.util import url_for
from indico.web.forms.fields import MultipleItemsField, OverrideMultipleItemsField, PrincipalListField

from indico_payment_cern import _
from indico_payment_cern.blueprint import blueprint
from indico_payment_cern.util import create_hash, get_order_id, get_payment_method, get_payment_methods


PAYMENT_METHODS_FIELDS = [{'id': 'name', 'caption': _("Name"), 'required': True},
                          {'id': 'title', 'caption': _("Displayed Name"), 'required': True},
                          {'id': 'type', 'caption': _("Type"), 'required': True},
                          {'id': 'fee', 'caption': _("Extra Fee (%)"), 'required': True},
                          {'id': 'disabled_currencies', 'caption': _("Disabled currencies"), 'required': False}]


class PluginSettingsForm(PaymentPluginSettingsFormBase):
    authorized_users = PrincipalListField(_('Authorized users'), allow_groups=True,
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
        super().__init__(*args, **kwargs)
        self.custom_fees.field_data = self._plugin_settings['payment_methods']


class CERNPaymentPlugin(PaymentPluginMixin, IndicoPlugin):
    """PostFinance CERN

    Providing a payment method using the PostFinance system.
    Extra fees can be set for each payment method so the price after the
    cut taken by the bank is the correct one.
    """
    configurable = True
    settings_form = PluginSettingsForm
    event_settings_form = EventSettingsForm
    default_settings = {'method_name': 'Credit Card',
                        'fp_email_address': '',
                        'fp_department_name': '',
                        'payment_url': '',
                        'shop_id_chf': '',
                        'shop_id_eur': '',
                        'hash_seed_chf': '',
                        'hash_seed_eur': '',
                        'hash_seed_out_chf': '',
                        'hash_seed_out_eur': '',
                        'server_url_suffix': '',
                        'order_id_prefix': '',
                        'payment_methods': []}
    acl_settings = {'authorized_users'}
    default_event_settings = {'enabled': False,
                              'method_name': None,
                              'apply_fees': True,
                              'custom_fees': {}}
    valid_currencies = {'EUR', 'CHF'}

    def init(self):
        super().init()
        self.template_hook('event-manage-payment-plugin-cannot-modify', self._get_cannot_modify_message)
        self.connect(signals.users.merged, self._merge_users)

    @property
    def logo_url(self):
        return url_for_plugin(self.name + '.static', filename='images/logo.png')

    def get_blueprints(self):
        return blueprint

    def can_be_modified(self, user, event):
        if user.is_admin:
            return True
        return self.settings.acls.contains_user('authorized_users', user)

    def _get_cannot_modify_message(self, plugin, event, **kwargs):
        if self != plugin:
            return
        fp_name = self.settings.get('fp_department_name')
        fp_email = self.settings.get('fp_email_address')
        return render_plugin_template('event_settings_readonly.html', fp_name=fp_name, fp_email=fp_email)

    def adjust_payment_form_data(self, data):
        data['postfinance_methods'] = get_payment_methods(data['event'], data['currency'])
        data['selected_method'] = selected_method = request.args.get('postfinance_method', '')
        base_amount = data['amount']
        if selected_method:
            method = get_payment_method(data['event'], data['currency'], selected_method)
            if method is None:
                raise UserValueError(_('Invalid currency'))
            modifier = Decimal(1 / (1 - method['fee'] / 100))
            data['amount'] = base_amount * modifier
            data['fee'] = data['amount'] - base_amount
            data['form_data'] = self._generate_form_data(data['amount'], data)
        else:
            data['form_data'] = None
            data['fee'] = None
            if data['event_settings']['apply_fees']:  # we don't know the final price
                data['amount'] = None

    def _get_order_id(self, data):
        return get_order_id(data['registration'], data['settings']['order_id_prefix'])

    def _generate_form_data(self, amount, data):
        if amount is None:
            return {}
        registration = data['registration']
        personal_data = registration.get_personal_data()
        event = data['event']
        currency = data['currency']
        seed = data['settings'][f'hash_seed_{currency.lower()}']
        shop_id = data['settings'][f'shop_id_{currency.lower()}']
        method = get_payment_method(event, currency, data['selected_method'])
        if method is None:
            raise UserValueError(_('Invalid currency'))
        template_page = ''  # yes, apparently it's supposed to be empty..
        template_hash = sha512((seed + template_page).encode()).hexdigest()
        order_id = self._get_order_id(data)
        locator = registration.locator.uuid

        address = re.sub(r'(\r?\n)+', ', ', personal_data.get('address', ''))
        form_data = {
            'PSPID': shop_id,
            'ORDERID': order_id,
            'AMOUNT': int(amount * 100),
            'CURRENCY': currency,
            'LANGUAGE': session.lang,
            'CN': str_to_ascii(remove_accents(registration.full_name[:35])),
            'EMAIL': registration.email[:50],
            'OWNERADDRESS': address[:35],
            'OWNERTELNO': personal_data.get('phone', '')[:30],
            'TP': template_page + '&hash=' + template_hash,
            'PM': method['type'],
            'BRAND': method['name'],
            'PARAMVAR': data['settings']['server_url_suffix'],
            'HOMEURL': url_for('event_registration.display_regform', locator, _external=True),
            'ACCEPTURL': url_for_plugin('payment_cern.success', locator, _external=True),
            'CANCELURL': url_for_plugin('payment_cern.cancel', locator, _external=True),
            'DECLINEURL': url_for_plugin('payment_cern.decline', locator, _external=True),
            'EXCEPTIONURL': url_for_plugin('payment_cern.uncertain', locator, _external=True),
            'BACKURL': url_for('payment.event_payment', locator, _external=True)
        }

        form_data['SHASIGN'] = create_hash(seed, form_data)
        return form_data

    def _merge_users(self, target, source, **kwargs):
        self.settings.acls.merge_users(target, source)
