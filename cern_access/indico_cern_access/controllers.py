from __future__ import unicode_literals

from flask import request

from indico.modules.events.registration.controllers import RegistrationFormMixin
from indico.modules.events.registration.controllers.management import RHManageRegFormsBase
from indico.modules.events.registration.models.registrations import Registration, RegistrationState

from indico_cern_access.models.access_requests import CERNAccessRequest, CERNAccessRequestState
from indico_cern_access.util import get_error_count, get_warning_count
from indico_cern_access.views import WPAccessRequestDetails


class RHCernAccessRequestsDetails(RegistrationFormMixin, RHManageRegFormsBase):

    def _checkParams(self, params):
        RHManageRegFormsBase._checkParams(self, params)
        RegistrationFormMixin._checkParams(self)

    def _process(self):
        return WPAccessRequestDetails.render_template('access_requests_details.html',
                                                      regform=self.regform,
                                                      access_state=CERNAccessRequestState,
                                                      error_count=get_error_count(self.regform),
                                                      warning_count=get_warning_count(self.regform),
                                                      registration_state=RegistrationState)
