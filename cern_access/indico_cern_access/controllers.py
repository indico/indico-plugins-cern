# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import redirect, request

from indico.core.db import db
from indico.modules.events.models.events import EventType
from indico.modules.events.registration.controllers.display import RHRegistrationFormRegistrationBase
from indico.modules.events.registration.controllers.management.reglists import RHRegistrationsActionBase
from indico.web.flask.util import url_for
from indico.web.util import jsonify_data

from indico_cern_access.forms import AccessIdentityDataForm
from indico_cern_access.util import grant_access, revoke_access, send_ticket
from indico_cern_access.views import WPAccessRequestDetailsConference, WPAccessRequestDetailsSimpleEvent


class RHRegistrationBulkCERNAccess(RHRegistrationsActionBase):
    """Bulk grant or revoke CERN access to registrations."""

    def _process(self):
        grant_cern_access = request.form['flag'] == '1'
        if grant_cern_access:
            grant_access(self.registrations, self.regform)
        else:
            revoke_access(self.registrations)
        return jsonify_data(**self.list_generator.render_list())


class RHRegistrationAccessIdentityData(RHRegistrationFormRegistrationBase):
    def _process(self):
        form = AccessIdentityDataForm()
        access_request = self.registration.cern_access_request
        if self.event.type_ == EventType.conference:
            view_class = WPAccessRequestDetailsConference
        else:
            view_class = WPAccessRequestDetailsSimpleEvent
        if access_request is not None and not access_request.has_identity_info and form.validate_on_submit():
            form.populate_obj(access_request)
            db.session.flush()
            send_ticket(self.registration)
            return redirect(url_for('plugin_cern_access.access_identity_data', self.registration.locator.uuid))
        return view_class.render_template('identity_data_form.html', self.event, form=form,
                                          access_request=access_request)
