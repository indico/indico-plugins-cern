# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask_pluginengine import current_plugin

from indico.util.string import remove_non_alpha, str_to_ascii


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


def get_order_id(registration, prefix, max_len=30):
    """Generates the order ID specific to a registration.

    Note: The format of the payment id in the end MUST NOT change
    as the finance department uses it to associate payments with
    events.  This is done manually using the event id, but any
    change to the format of the order ID should be checked with them
    beforehand.
    """
    payment_id = f'c{registration.event_id}r{registration.id}'
    order_id_extra_len = max_len - len(payment_id)
    order_id = prefix + remove_non_alpha(str_to_ascii(registration.last_name + registration.first_name))
    return order_id[:order_id_extra_len].upper().strip() + payment_id
