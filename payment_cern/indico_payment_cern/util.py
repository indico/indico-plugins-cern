# This file is part of Indico.
# Copyright (C) 2002 - 2015 European Organization for Nuclear Research (CERN).
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# Indico is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Indico; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from flask_pluginengine import current_plugin


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
