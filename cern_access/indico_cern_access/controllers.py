from __future__ import unicode_literals

from indico.modules.events.registration.controllers import RegistrationFormMixin
from indico.modules.events.registration.controllers.management import RHManageRegFormsBase

from indico_cern_access.models.access_requests import CERNAccessRequestState
from indico_cern_access.views import WPAccessRequestDetails


class RHCernAccessRequestsDetails(RegistrationFormMixin, RHManageRegFormsBase):

    def _checkParams(self, params):
        RHManageRegFormsBase._checkParams(self, params)
        RegistrationFormMixin._checkParams(self)

    def _process(self):
        return WPAccessRequestDetails.render_template('access_requests_details.html',
                                                      regform=self.regform,
                                                      state=CERNAccessRequestState)
