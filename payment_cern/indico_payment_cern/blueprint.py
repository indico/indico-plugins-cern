# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_payment_cern.controllers import (RHPostFinanceCheckIndicoTransaction, RHPostFinanceInitPayment,
                                             RHPostFinanceReturn, RHPostFinanceWebhook)


blueprint = IndicoPluginBlueprint(
    'payment_cern', __name__,
    url_prefix='/event/<int:event_id>/registrations/<int:reg_form_id>/payment'
)
# PostFinance Checkout callb
blueprint.add_url_rule('/cern/init', 'init', RHPostFinanceInitPayment, methods=('POST',))
blueprint.add_url_rule('/cern/return', 'return', RHPostFinanceReturn)
blueprint.add_url_rule('/cern/check-transaction', 'check_transaction', RHPostFinanceCheckIndicoTransaction)
blueprint.add_url_rule('!/payment/cern/postfinance-webhook', 'pf_webhook', RHPostFinanceWebhook, methods=('POST',))
