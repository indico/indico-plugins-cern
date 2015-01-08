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

from indico.core.plugins import IndicoPluginBlueprint
from indico_payment_cern.controllers import (RHPaymentCancel, RHPaymentDecline, RHPaymentUncertain, RHPaymentSuccess,
                                             RHPaymentSuccessBackground, RHPaymentCancelBackground)


blueprint = IndicoPluginBlueprint('payment_cern', __name__,
                                  url_prefix='/event/<confId>/registration/payment/response/cern')
blueprint.add_url_rule('/cancel', 'cancel', RHPaymentCancel, methods=('GET', 'POST'))
blueprint.add_url_rule('/decline', 'decline', RHPaymentDecline, methods=('GET', 'POST'))
blueprint.add_url_rule('/uncertain', 'uncertain', RHPaymentUncertain, methods=('GET', 'POST'))
blueprint.add_url_rule('/success', 'success', RHPaymentSuccess, methods=('GET', 'POST'))
# ID-less URL for the callback where we cannot customize anything besides a single variable
blueprint.add_url_rule('!/payment/cern/success', 'background-success', RHPaymentSuccessBackground,
                       methods=('GET', 'POST'))
blueprint.add_url_rule('!/payment/cern/cancel', 'background-cancel', RHPaymentCancelBackground,
                       methods=('GET', 'POST'))
