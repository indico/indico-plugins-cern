# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from decimal import Decimal

from flask_pluginengine import current_plugin
from postfinancecheckout import Configuration
from postfinancecheckout.api import TransactionPaymentPageServiceApi, TransactionServiceApi
from postfinancecheckout.models import (AddressCreate, LineItem, LineItemType, TransactionCreate,
                                        TransactionEnvironmentSelectionStrategy)
from postfinancecheckout.rest import ApiException

from indico.core.config import config as indico_config
from indico.util.string import slugify
from indico.web.flask.util import url_for

from indico_payment_cern.util import get_order_id


# XXX should those be configurable or even queried from the API? If we have to query them, this code
# does the job, but they are also listed on https://checkout.postfinance.ch/doc/api/payment-method-brand/list
# for meth in PaymentMethodBrandServiceApi(config).all():
#     meth = meth.to_dict()
#     meth.pop('description')
#     meth['name'] = meth['name']['en-US']
#     print(meth['id'], meth['name'])
POSTFINANCE_METHOD_IDS = {
    'visa': 1461144365052,
    'mastercard': 1461144371207,
    'american express': 1461144377346,
    'postfinance card': 1461144402291,
}


def _get_pf_config():
    space_id = current_plugin.settings.get('postfinance_space_id')
    config = Configuration(user_id=current_plugin.settings.get('postfinance_user_id'),
                           api_secret=current_plugin.settings.get('postfinance_api_secret'))
    return config, space_id


def create_pf_transaction(registration, payment_method):
    if current_plugin.event_settings.get(registration.event, 'apply_fees'):
        # This calculation seems completely nuts for a percentage-based fee at first, but it indeed
        # correct since the percentage is subtracted from the total amount paid - so we need to get
        # a total price that, after subtracting x%, results in the actual price of the registration.
        modifier = Decimal(1 / (1 - payment_method['fee'] / 100))
        total_amount = round(registration.price * modifier, 2)
        payment_method_fee = total_amount - registration.price
    else:
        payment_method_fee = 0

    try:
        pf_payment_method_id = POSTFINANCE_METHOD_IDS[payment_method['name'].lower()]
    except KeyError:
        raise RuntimeError(f'Unknown payment method: {payment_method["name"]}')

    # create line items for the payment
    line_items = []
    line_items.append(LineItem(
        name='Registration',
        unique_id='reg',
        quantity=1,
        amount_including_tax=float(round(registration.price, 2)),
        type=LineItemType.PRODUCT
    ))
    method_fee = 0
    if payment_method_fee:
        method_fee = float(round(payment_method_fee, 2))
        line_items.append(LineItem(
            name='Extra fee',
            unique_id=f'fee-{slugify(payment_method["name"])}',
            quantity=1,
            amount_including_tax=method_fee,
            type=LineItemType.FEE
        ))

    personal_data = registration.get_personal_data()
    order_id = get_order_id(registration, current_plugin.settings.get('order_id_prefix'), max_len=100)
    registration_url = url_for('.return', registration.locator.registrant, _external=True)
    env_strategy = (current_plugin.settings.get('postfinance_env_strategy')
                    if not current_plugin.event_settings.get(registration.event, 'force_test_mode')
                    else TransactionEnvironmentSelectionStrategy.FORCE_TEST_ENVIRONMENT)

    address = AddressCreate(
        given_name=personal_data['first_name'],
        family_name=personal_data['last_name'],
        email_address=personal_data['email'],
    )
    transaction_create = TransactionCreate(
        line_items=line_items,
        auto_confirmation_enabled=True,
        merchant_reference=order_id,
        currency=registration.currency,
        billing_address=address,
        allowed_payment_method_brands=[pf_payment_method_id],
        environment_selection_strategy=env_strategy,
        success_url=registration_url,
        failed_url=registration_url,
        meta_data={
            'indico_url': indico_config.BASE_URL,
            'event_id': registration.event.id,
            'registration_id': registration.id,
            'order_id': order_id,
            'payment_method_name': payment_method['name'],
            'payment_method_title': payment_method['title'],
            'method_fee': method_fee,
        }
    )

    config, space_id = _get_pf_config()
    transaction_svc = TransactionServiceApi(config)
    txn_payment_page_svc = TransactionPaymentPageServiceApi(config)

    try:
        transaction = transaction_svc.create(space_id=space_id, transaction=transaction_create)
        payment_page_url = txn_payment_page_svc.payment_page_url(space_id=space_id, id=transaction.id)
    except ApiException as exc:
        raise RuntimeError('Could not initialize payment') from exc
    current_plugin.logger.info('Initialized transaction %d for %r --> %s', transaction.id, registration,
                               payment_page_url)
    return payment_page_url


def get_pf_transaction(transaction_id):
    config, space_id = _get_pf_config()
    transaction_svc = TransactionServiceApi(config)
    transaction = transaction_svc.read(space_id, transaction_id)
    if transaction is None or transaction.id is None:
        # weird API, returns an object with all the fields set to None. it never returns None for
        # the transaction itself but let's handle this as well in case they ever change this
        raise RuntimeError(f'Could not get transaction {transaction_id}')
    return transaction
