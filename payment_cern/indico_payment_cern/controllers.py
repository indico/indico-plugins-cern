from __future__ import unicode_literals

import re

from flask import request, flash, redirect
from flask_pluginengine import current_plugin, render_plugin_template
from markupsafe import Markup
from werkzeug.exceptions import BadRequest

from indico.modules.payment.models.transactions import TransactionAction, PaymentTransaction
from indico.modules.payment.util import register_transaction, get_registrant_params
from indico.web.flask.util import url_for
from MaKaC.conference import ConferenceHolder
from MaKaC.webinterface.rh.base import RH
from MaKaC.webinterface.rh.registrationFormDisplay import RHRegistrationFormRegistrantBase

from indico_payment_cern import _
from indico_payment_cern.util import create_hash


class RHPaymentAbortedBase(RHRegistrationFormRegistrantBase):
    """Base class for simple payment errors which just show a message"""
    _category = 'info'
    _msg = None

    def _process(self):
        flash(self._msg, self._category)
        return redirect(url_for('event.confRegistrationFormDisplay', self._conf))


class RHPaymentCancel(RHPaymentAbortedBase):
    _msg = _('You cancelled the payment process.')


class RHPaymentDecline(RHPaymentAbortedBase):
    _category = 'error'
    _msg = _('Your payment was declined.')


class RHPaymentUncertain(RHPaymentAbortedBase):
    _category = 'error'

    @property
    def _msg(self):
        return Markup(render_plugin_template('payment_uncertain.html', settings=current_plugin.settings.get_all(),
                                             registrant=self._registrant, event=self._conf))


class PaymentSuccessMixin:
    def _check_hash(self):
        if bool(request.form) == bool(request.args):
            # Prevent tampering with GET/POST data. We expect only one type of arguments!
            # The signature check would fail anyway but if someone tries to be smart we'll log it here.
            current_plugin.logger.error('Received invalid request from postfinance containing GET and '
                                        'POST data ({}, {})'.format(request.args, request.form))
            raise BadRequest
        fields = {'AAVCheck', 'ACCEPTANCE', 'BRAND', 'CARDNO', 'CCCTY', 'CN', 'CVCCheck', 'ECI', 'ED', 'IP', 'IPCTY',
                  'NCERROR', 'PAYID', 'PM', 'STATUS', 'TRXDATE', 'VC', 'amount', 'currency', 'orderID'}
        seed = current_plugin.settings.get('hash_seed_out_{}'.format(request.values['currency'].lower()))
        expected_hash = create_hash(seed, {k.upper(): v for k, v in request.values.iteritems() if k in fields})
        return request.values['SHASIGN'] == expected_hash

    def _create_transaction(self):
        amount = float(request.values['amount'])
        currency = request.values['currency']
        request_data = request.values.to_dict()
        transaction = PaymentTransaction.find_latest_for_registrant(self.registrant)
        if transaction and transaction.data == request_data:
            # Same request, e.g. because of the client-side and server-side success notification
            return
        register_transaction(registrant=self.registrant,
                             amount=amount,
                             currency=currency,
                             action=TransactionAction.complete,
                             provider='cern',
                             data=request_data)


class RHPaymentSuccess(PaymentSuccessMixin, RHRegistrationFormRegistrantBase):
    """Verify and process a successful payment"""

    def _checkParams(self, params):
        RHRegistrationFormRegistrantBase._checkParams(self, params)
        self.event = self._conf
        self.registrant = self._registrant

    def _process(self):
        if not self._check_hash():
            flash('Your transaction could not be authorized.', 'error')
            return redirect(url_for('event.confRegistrationFormDisplay', self.event, **get_registrant_params()))

        self._create_transaction()
        flash(_('Your payment request has been processed.'), 'success')
        return redirect(url_for('event.confRegistrationFormDisplay', self.event, **get_registrant_params()))


class RHPaymentSuccessBackground(PaymentSuccessMixin, RH):
    """Verify and process a successful payment (server2server notification)"""

    def _checkParams(self):
        matches = re.search(r'c(\d+)r(\d+)$', request.values['orderID'])
        if matches is None:
            raise BadRequest
        self.event = ConferenceHolder().getById(matches.group(1), quiet=True)
        if not self.event:
            raise BadRequest
        self.registrant = self.event.getRegistrantById(matches.group(2))
        if not self.registrant:
            raise BadRequest

    def _process(self):
        if not self._check_hash():
            current_plugin.logger.warning('Received invalid request from postfinance: {}'.format(request.values))
            raise BadRequest

        self._create_transaction()


class RHPaymentCancelBackground(RH):
    """Request cancelled callback (server2server notification)"""

    def _process(self):
        # We don't do anything here since we don't have anything stored locally
        # for a transaction that was not successful.
        pass
