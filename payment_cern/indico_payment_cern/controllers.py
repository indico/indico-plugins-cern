# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re

from flask import flash, redirect, request
from flask_pluginengine import current_plugin, render_plugin_template
from markupsafe import Markup
from werkzeug.exceptions import BadRequest

from indico.modules.events.payment.models.transactions import TransactionAction
from indico.modules.events.payment.util import register_transaction
from indico.modules.events.registration.controllers.display import RHRegistrationFormRegistrationBase
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.web.flask.util import url_for
from indico.web.rh import RH

from indico_payment_cern import _
from indico_payment_cern.util import create_hash


class RHPaymentAbortedBase(RHRegistrationFormRegistrationBase):
    """Base class for simple payment errors which just show a message"""

    _category = 'info'
    _msg = None
    CSRF_ENABLED = False

    def _process(self):
        flash(self._msg, self._category)
        return redirect(url_for('event_registration.display_regform', self.registration.locator.registrant))


class RHPaymentCancel(RHPaymentAbortedBase):
    _msg = _('You cancelled the payment process.')


class RHPaymentDecline(RHPaymentAbortedBase):
    _category = 'error'
    _msg = _('Your payment was declined.')


class RHPaymentUncertain(RHPaymentAbortedBase):
    _category = 'error'

    @property
    def _msg(self):
        return Markup(render_plugin_template('payment_uncertain.html', registration=self.registration,
                                             settings=current_plugin.settings.get_all()))


class PaymentSuccessMixin:
    CSRF_ENABLED = False

    def _check_hash(self):
        if bool(request.form) == bool(request.args):
            # Prevent tampering with GET/POST data. We expect only one type of arguments!
            # The signature check would fail anyway but if someone tries to be smart we'll log it here.
            current_plugin.logger.error('Received invalid request from postfinance containing GET and '
                                        'POST data (%s, %s)', request.args, request.form)
            raise BadRequest
        fields = {'AAVCheck', 'ACCEPTANCE', 'BRAND', 'CARDNO', 'CCCTY', 'CN', 'CVCCheck', 'ECI', 'ED', 'IP', 'IPCTY',
                  'NCERROR', 'PAYID', 'PM', 'STATUS', 'TRXDATE', 'VC', 'amount', 'currency', 'orderID'}
        seed = current_plugin.settings.get('hash_seed_out_{}'.format(request.values['currency'].lower()))
        expected_hash = create_hash(seed, {k.upper(): v for k, v in request.values.items() if k in fields})
        return request.values['SHASIGN'] == expected_hash

    def _create_transaction(self):
        amount = float(request.values['amount'])
        currency = request.values['currency']
        request_data = request.values.to_dict()
        transaction = self.registration.transaction
        if transaction and transaction.data == request_data:
            # Same request, e.g. because of the client-side and server-side success notification
            return
        if self.registration.state != RegistrationState.complete:
            register_transaction(registration=self.registration,
                                 amount=amount,
                                 currency=currency,
                                 action=TransactionAction.complete,
                                 provider='cern',
                                 data=request_data)


class RHPaymentSuccess(PaymentSuccessMixin, RHRegistrationFormRegistrationBase):
    """Verify and process a successful payment"""

    def _process(self):
        if not self._check_hash():
            flash('Your transaction could not be authorized.', 'error')
        else:
            self._create_transaction()
            flash(_('Your payment request has been processed.'), 'success')
        return redirect(url_for('event_registration.display_regform', self.registration.locator.registrant))


class RHPaymentSuccessBackground(PaymentSuccessMixin, RH):
    """Verify and process a successful payment (server2server notification)"""

    def _process_args(self):
        matches = re.search(r'r(\d+)$', request.values['orderID'])
        if matches is None:
            raise BadRequest
        self.registration = Registration.find_first(id=matches.group(1))
        if self.registration is None:
            raise BadRequest

    def _process(self):
        if not self._check_hash():
            current_plugin.logger.warning('Received invalid request from postfinance: %s', request.values)
            raise BadRequest
        self._create_transaction()


class RHPaymentCancelBackground(RH):
    """Request cancelled callback (server2server notification)"""

    CSRF_ENABLED = False

    def _process(self):
        # We don't do anything here since we don't have anything stored locally
        # for a transaction that was not successful.
        pass
