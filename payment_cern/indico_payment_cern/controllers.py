# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
import re
from datetime import datetime

from flask import flash, jsonify, redirect, request
from flask_pluginengine import current_plugin, render_plugin_template
from markupsafe import Markup
from marshmallow import fields
from postfinancecheckout.models import TransactionState as PostFinanceTransactionState
from werkzeug.exceptions import BadRequest, Unauthorized

from indico.core.config import config
from indico.core.errors import UserValueError
from indico.modules.events.payment.controllers import RHPaymentBase
from indico.modules.events.payment.models.transactions import TransactionAction, TransactionStatus
from indico.modules.events.payment.util import register_transaction
from indico.modules.events.registration.controllers.display import RHRegistrationFormRegistrationBase
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.web.args import use_kwargs
from indico.web.flask.util import url_for
from indico.web.rh import RH, custom_auth

from indico_payment_cern import _
from indico_payment_cern.postfinance import create_pf_transaction, get_pf_transaction
from indico_payment_cern.util import create_hash, get_payment_method
from indico_payment_cern.views import WPPaymentEventCERN


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
        self.registration = Registration.query.filter_by(id=matches.group(1)).first()
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


class RHPostFinanceInitPayment(RHPaymentBase):
    """Initialize the new PostFinance Checkout payment flow."""

    @use_kwargs({
        'postfinance_method': fields.String(required=True),
    })
    def _process(self, postfinance_method):
        method = get_payment_method(self.event, self.registration.currency, postfinance_method)
        if method is None:
            raise UserValueError(_('Invalid currency'))
        payment_page_url = create_pf_transaction(self.registration, method)
        return redirect(payment_page_url)


class RHPostFinanceReturn(RHPaymentBase):
    """Show a waiting page after being returned from the payment page."""

    def _process(self):
        if not (txn := self.registration.transaction):
            # Likely the user cancelled straight away, in that case no transaction is created on the Indico side
            return redirect(url_for('event_registration.display_regform', self.registration.locator.registrant))

        if txn.status == TransactionStatus.pending:
            return WPPaymentEventCERN.render_template('postfinance_return.html', self.event,
                                                      regform=self.regform, registration=self.registration)

        if txn.status == TransactionStatus.successful:
            flash(_('Your payment has been processed.'), 'success')
        elif txn.status == TransactionStatus.rejected:
            flash(_('Your payment was unsuccessful. Please retry or get in touch with the event organizers.'), 'error')

        return redirect(url_for('event_registration.display_regform', self.registration.locator.registrant))


class RHPostFinanceCheckIndicoTransaction(RHPaymentBase):
    """Check if the registration's transaction is still pending.

    This is used on the return page to poll whether to send the user back to the
    registration page or keep checking.
    """

    def _process(self):
        txn = self.registration.transaction
        is_pending = txn is not None and txn.status == TransactionStatus.pending
        return jsonify(pending=is_pending)


@custom_auth
class RHPostFinanceWebhook(RH):
    """Webhook sent by the postfinance backend.

    The webhook should be set to include the following states:

    - Fulfill
    - Failed
    - Processing
    - Decline
    - Voided

    Other states should NOT be included, because PostFinance only lets you query the current
    state of the transaction, and by the time a webhook arrives it may have progressed to a
    later state. This causes nasty SQL deadlock warnings so by only subscribing to the most
    important events we can avoid that.
    """

    CSRF_ENABLED = False

    def _check_access(self):
        if (secret := current_plugin.settings.get('postfinance_webhook_secret')) and request.bearer_token != secret:
            current_plugin.logger.warning('Received postfinance webhook without a valid bearer token')
            raise Unauthorized('Invalid bearer token')

    @use_kwargs({
        'entity_name': fields.String(data_key='listenerEntityTechnicalName', required=True),
        'entity_id': fields.Integer(data_key='entityId', required=True),
    })
    def _process(self, entity_name, entity_id):
        if entity_name != 'Transaction':
            raise BadRequest('Unexpected entity name')

        pf_txn = get_pf_transaction(entity_id)
        if pf_txn.meta_data['indico_url'] != config.BASE_URL:
            current_plugin.logger.info('Ignoring webhook for different indico instance (%s != %s)',
                                       pf_txn.meta_data['indico_url'], config.BASE_URL)
            return '', 204

        if pf_txn.state == PostFinanceTransactionState.PROCESSING:
            self._register_processing(pf_txn)
        elif pf_txn.state == PostFinanceTransactionState.FULFILL:
            self._register_success(pf_txn)
        elif pf_txn.state in {PostFinanceTransactionState.FAILED, PostFinanceTransactionState.DECLINE,
                              PostFinanceTransactionState.VOIDED}:
            # Note: Unlike documented (https://checkout.postfinance.ch/en-us/doc/payment/transaction-process#_failed),
            # the "failed" state is NOT final. It happens when 3D-Secure fails, but the user can retry (e.g. with a
            # different card) and still cause a successful transaction.
            self._register_failure(pf_txn)

        return '', 204

    def _get_registration(self, pf_txn):
        return Registration.query.get_or_404(int(pf_txn.meta_data['registration_id']))

    def _fix_datetimes(self, data):
        def _default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            raise TypeError(f'Object of type {o.__class__.__name__} is not JSON serializable')
        return json.loads(json.dumps(data, default=_default))

    def _register_processing(self, pf_txn):
        registration = self._get_registration(pf_txn)
        if registration.state != RegistrationState.complete:
            register_transaction(registration=registration,
                                 amount=pf_txn.authorization_amount,
                                 currency=pf_txn.currency,
                                 action=TransactionAction.pending,
                                 provider='cern',
                                 data=self._fix_datetimes(pf_txn.to_dict()))

    def _register_failure(self, pf_txn):
        registration = self._get_registration(pf_txn)
        if registration.state != RegistrationState.complete:
            register_transaction(registration=registration,
                                 amount=pf_txn.authorization_amount,
                                 currency=pf_txn.currency,
                                 action=TransactionAction.reject,
                                 provider='cern',
                                 data=self._fix_datetimes(pf_txn.to_dict()))

    def _register_success(self, pf_txn):
        registration = self._get_registration(pf_txn)
        transaction = registration.transaction
        pf_txn_data = self._fix_datetimes(pf_txn.to_dict())
        if transaction and transaction.data == pf_txn_data:
            current_plugin.logger.warning('Ignoring duplicate webhook call with same data')
            return
        if registration.state != RegistrationState.complete:
            register_transaction(registration=registration,
                                 amount=pf_txn.completed_amount,
                                 currency=pf_txn.currency,
                                 action=TransactionAction.complete,
                                 provider='cern',
                                 data=pf_txn_data)
