# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import json
from datetime import datetime

from flask import flash, jsonify, redirect, request
from flask_pluginengine import current_plugin
from marshmallow import fields
from postfinancecheckout.models import TransactionState as PostFinanceTransactionState
from werkzeug.exceptions import BadRequest, Unauthorized

from indico.core.config import config
from indico.core.errors import UserValueError
from indico.modules.events.payment.controllers import RHPaymentBase
from indico.modules.events.payment.models.transactions import TransactionAction, TransactionStatus
from indico.modules.events.payment.util import register_transaction
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.web.args import use_kwargs
from indico.web.flask.util import url_for
from indico.web.rh import RH, custom_auth

from indico_payment_cern import _
from indico_payment_cern.postfinance import create_pf_transaction, get_pf_transaction
from indico_payment_cern.util import get_payment_method
from indico_payment_cern.views import WPPaymentEventCERN


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
