from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint
from indico_payment_cern.controllers import (RHPaymentCancel, RHPaymentDecline, RHPaymentUncertain, RHPaymentSuccess,
                                             RHPaymentSuccessBackground, RHPaymentCancelBackground)


blueprint = IndicoPluginBlueprint('payment_cern', __name__,
                                  url_prefix='/event/<confId>/registrations/<int:reg_form_id>/payment/response/cern')
blueprint.add_url_rule('/cancel', 'cancel', RHPaymentCancel, methods=('GET', 'POST'))
blueprint.add_url_rule('/decline', 'decline', RHPaymentDecline, methods=('GET', 'POST'))
blueprint.add_url_rule('/uncertain', 'uncertain', RHPaymentUncertain, methods=('GET', 'POST'))
blueprint.add_url_rule('/success', 'success', RHPaymentSuccess, methods=('GET', 'POST'))
# ID-less URL for the callback where we cannot customize anything besides a single variable
blueprint.add_url_rule('!/payment/cern/success', 'background-success', RHPaymentSuccessBackground,
                       methods=('GET', 'POST'))
blueprint.add_url_rule('!/payment/cern/cancel', 'background-cancel', RHPaymentCancelBackground,
                       methods=('GET', 'POST'))
