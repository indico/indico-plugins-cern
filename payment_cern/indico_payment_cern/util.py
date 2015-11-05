from __future__ import unicode_literals

from hashlib import sha512

from flask_pluginengine import current_plugin

from indico.util.string import remove_non_alpha, remove_accents


def get_payment_methods(event):
    """Returns the available payment methods with the correct fees.

    :return: a list containing the payment methods with the correct fees
    """
    methods = []
    apply_fees = current_plugin.event_settings.get(event, 'apply_fees')
    custom_fees = current_plugin.event_settings.get(event, 'custom_fees')
    for method in current_plugin.settings.get('payment_methods'):
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


def get_payment_method(event, name):
    """Returns a specific payment method with the correct fee"""
    return next(x for x in get_payment_methods(event) if x['name'] == name)


def create_hash(seed, form_data):
    """Creates the weird hash for postfinance"""
    data_str = seed.join('{}={}'.format(key, value) for key, value in sorted(form_data.items()) if value) + seed
    return sha512(data_str).hexdigest().upper()


def get_order_id(registration, prefix):
    """Generates the order ID specific to a registration.

    Note: The format of the payment id in the end MUST NOT change
    as the finance department uses it to associate payments with
    events.  This is done manually using the event id, but any
    change to the format of the order ID should be checked with them
    beforehand.
    """
    payment_id = 'c{}r{}'.format(registration.event_id, registration.id)
    order_id_extra_len = 30 - len(payment_id)
    order_id = prefix + remove_non_alpha(remove_accents(registration.last_name + registration.first_name))
    return order_id[:order_id_extra_len].upper().strip() + payment_id
