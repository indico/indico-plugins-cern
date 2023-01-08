# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from hashlib import sha512

from flask_pluginengine import current_plugin

from indico.util.string import remove_accents, remove_non_alpha


def get_payment_methods(event, currency):
    """Returns the available payment methods with the correct fees.

    :return: a list containing the payment methods with the correct fees
    """
    methods = []
    apply_fees = current_plugin.event_settings.get(event, 'apply_fees')
    custom_fees = current_plugin.event_settings.get(event, 'custom_fees')
    for method in current_plugin.settings.get('payment_methods'):
        if currency in method.get('disabled_currencies', '').split(','):
            continue
        if apply_fees:
            try:
                fee = float(custom_fees[method['name']]['fee'])
            except KeyError:
                fee = float(method['fee'])
        else:
            fee = 0
        method['fee'] = fee
        methods.append(method)
    return methods


def get_payment_method(event, currency, name):
    """Returns a specific payment method with the correct fee"""
    return next((x for x in get_payment_methods(event, currency) if x['name'] == name), None)


def create_hash(seed, form_data):
    """Creates the weird hash for postfinance"""
    data_str = seed.join(f'{key}={value}' for key, value in sorted(form_data.items()) if value) + seed
    return sha512(data_str.encode()).hexdigest().upper()


def get_order_id(registration, prefix):
    """Generates the order ID specific to a registration.

    Note: The format of the payment id in the end MUST NOT change
    as the finance department uses it to associate payments with
    events.  This is done manually using the event id, but any
    change to the format of the order ID should be checked with them
    beforehand.
    """
    payment_id = f'c{registration.event_id}r{registration.id}'
    order_id_extra_len = 30 - len(payment_id)
    order_id = prefix + remove_non_alpha(remove_accents(registration.last_name + registration.first_name))
    return order_id[:order_id_extra_len].upper().strip() + payment_id
