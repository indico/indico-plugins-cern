# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from decimal import Decimal

from flask import request
from flask_pluginengine import render_plugin_template
from postfinancecheckout.models import TransactionEnvironmentSelectionStrategy
from wtforms.fields import BooleanField, EmailField, StringField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.errors import UserValueError
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.modules.events.payment import (PaymentEventSettingsFormBase, PaymentPluginMixin,
                                           PaymentPluginSettingsFormBase)
from indico.modules.users import EnumConverter
from indico.web.forms.fields import (IndicoEnumSelectField, MultipleItemsField, OverrideMultipleItemsField,
                                     PrincipalListField)

from indico_payment_cern import _
from indico_payment_cern.blueprint import blueprint
from indico_payment_cern.util import get_payment_method, get_payment_methods


PAYMENT_METHODS_FIELDS = [{'id': 'name', 'caption': _('Name'), 'required': True},
                          {'id': 'title', 'caption': _('Displayed Name'), 'required': True},
                          {'id': 'type', 'caption': _('Type'), 'required': True},
                          {'id': 'fee', 'caption': _('Extra Fee (%)'), 'required': True},
                          {'id': 'disabled_currencies', 'caption': _('Disabled currencies'), 'required': False}]


PF_ENV_STRATEGIES = {
    TransactionEnvironmentSelectionStrategy.FORCE_TEST_ENVIRONMENT: _('Force test'),
    TransactionEnvironmentSelectionStrategy.FORCE_PRODUCTION_ENVIRONMENT: _('Force production'),
    TransactionEnvironmentSelectionStrategy.USE_CONFIGURATION: _('Use configuration'),
}


class PluginSettingsForm(PaymentPluginSettingsFormBase):
    _fieldsets = [
        (_('General'), [
            'authorized_users', 'fp_email_address', 'fp_department_name', 'order_id_prefix', 'payment_methods',
        ]),
        (_('PostFinance Checkout'), [
            'postfinance_space_id', 'postfinance_user_id', 'postfinance_api_secret', 'postfinance_webhook_secret',
            'postfinance_env_strategy',
        ]),
    ]

    # General
    authorized_users = PrincipalListField(_('Authorized users'), allow_groups=True,
                                          description=_('List of users/groups who are authorized to configure the CERN '
                                                        'Payment module for any event.'))
    fp_email_address = EmailField(_('FP email adress'), [DataRequired()], description=_('Email address to contact FP.'))
    fp_department_name = StringField(_('FP department name'), [DataRequired()])
    order_id_prefix = StringField(_('Order ID Prefix'))
    payment_methods = MultipleItemsField(_('Payment Methods'), fields=PAYMENT_METHODS_FIELDS, unique_field='name')
    # Postfinance Checkout
    postfinance_space_id = StringField(_('PostFinance space ID'), [DataRequired()])
    postfinance_user_id = StringField(_('PostFinance user ID'), [DataRequired()])
    postfinance_api_secret = StringField(_('PostFinance API secret'), [DataRequired()])
    postfinance_webhook_secret = StringField(_('Webhook secret'),
                                             description=_('If set, the webhook URL on postfinance must be configured '
                                                           'to send "Bearer YOUR SECRET" as the Authorization header'))
    postfinance_env_strategy = IndicoEnumSelectField(_('Environment strategy'), [DataRequired()],
                                                     enum=TransactionEnvironmentSelectionStrategy,
                                                     titles=PF_ENV_STRATEGIES)


class EventSettingsForm(PaymentEventSettingsFormBase):
    apply_fees = BooleanField(_('Apply fees'), description=_('Enables the payment method specific fees.'))
    custom_fees = OverrideMultipleItemsField(_('Payment Methods'), fields=PAYMENT_METHODS_FIELDS, unique_field='name',
                                             edit_fields=['fee'],
                                             description=_('Here the fees of the various payment methods can be '
                                                           'overridden.'))
    force_test_mode = BooleanField(_('Force test mode'),
                                   description=_("Uses Postfinance's test mode (no real money involved)"))

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
                        'order_id_prefix': '',
                        'payment_methods': [],
                        'postfinance_space_id': '',
                        'postfinance_user_id': '',
                        'postfinance_api_secret': '',
                        'postfinance_webhook_secret': '',
                        'postfinance_env_strategy': TransactionEnvironmentSelectionStrategy.USE_CONFIGURATION}
    acl_settings = {'authorized_users'}
    settings_converters = {
        'postfinance_env_strategy': EnumConverter(TransactionEnvironmentSelectionStrategy),
    }
    default_event_settings = {'enabled': False,
                              'method_name': None,
                              'apply_fees': True,
                              'custom_fees': {},
                              'force_test_mode': False}
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
        else:
            data['fee'] = None
            if data['event_settings']['apply_fees']:  # we don't know the final price
                data['amount'] = None

    def _merge_users(self, target, source, **kwargs):
        self.settings.acls.merge_users(target, source)
