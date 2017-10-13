from __future__ import unicode_literals

from flask import request

from indico.modules.events.registration.controllers.management.reglists import RHRegistrationsActionBase
from indico.web.util import jsonify_data

from indico_cern_access.util import grant_access, revoke_access


class RHRegistrationBulkCERNAccess(RHRegistrationsActionBase):
    """Bulk grant or revoke CERN access to registrations"""

    def _process(self):
        grant_cern_access = request.form['flag'] == '1'
        if grant_cern_access:
            grant_access(self.registrations, self.regform)
        else:
            revoke_access(self.registrations)
        return jsonify_data(**self.list_generator.render_list())
