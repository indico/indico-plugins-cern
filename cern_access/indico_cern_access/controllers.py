# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import redirect, request
from flask_pluginengine import render_plugin_template

from indico.core.db import db
from indico.core.errors import UserValueError
from indico.modules.events.registration.controllers.display import RHRegistrationFormRegistrationBase
from indico.modules.events.registration.controllers.management import RHManageRegistrationBase
from indico.modules.events.registration.controllers.management.reglists import RHRegistrationsActionBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.requests.controllers import RHRequestsEventRequestDetailsBase
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.web.flask.util import url_for
from indico.web.util import jsonify_data, jsonify_template

from indico_cern_access import _
from indico_cern_access.forms import AccessIdentityDataForm
from indico_cern_access.util import get_access_dates, get_last_request, grant_access, revoke_access, send_ticket
from indico_cern_access.views import WPAccessRequestDetails


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
        if access_request is not None and not access_request.has_identity_info and form.validate_on_submit():
            form.populate_obj(access_request)
            db.session.flush()
            send_ticket(self.registration)
            return redirect(url_for('.access_identity_data', self.registration.locator.uuid))

        start_dt, end_dt = get_access_dates(get_last_request(self.event))
        return WPAccessRequestDetails.render_template('identity_data_form.html', self.event, form=form,
                                                      access_request=access_request, start_dt=start_dt, end_dt=end_dt)


class RHRegistrationEnterIdentityData(RHManageRegistrationBase):
    def _process(self):
        access_request = self.registration.cern_access_request
        if not access_request or access_request.has_identity_info:
            raise UserValueError(_('The personal data for this registrant has already been entered'))
        form = AccessIdentityDataForm()
        if form.validate_on_submit():
            form.populate_obj(access_request)
            db.session.flush()
            send_ticket(self.registration)
            return jsonify_data(html=render_plugin_template('cern_access_status.html', registration=self.registration,
                                                            header=False))
        return jsonify_template('identity_data_form_management.html', render_plugin_template, form=form,
                                registration=self.registration)


class RHExportCERNAccessBase(RHRequestsEventRequestDetailsBase):
    def _process_args(self):
        RHRequestsEventRequestDetailsBase._process_args(self)
        self.regform = (RegistrationForm.query.with_parent(self.event)
                        .filter_by(id=request.view_args['reg_form_id'])
                        .one())

    def _get_cern_access_flag(self, registration):
        if not self.regform.cern_access_request or not self.regform.cern_access_request.is_active:
            return 'n/a'
        access_request = registration.cern_access_request
        if not access_request:
            return 'Not requested'
        elif access_request.is_withdrawn:
            return 'Revoked'
        elif not access_request.has_identity_info:
            return 'Personal data missing'
        else:
            return 'Granted'

    def _generate_spreadsheet(self):
        registrations = (Registration.query.with_parent(self.regform)
                         .filter(~Registration.is_deleted)
                         .order_by(*Registration.order_by_name)
                         .all())
        column_names = ['Id', 'First Name', 'Last Name', 'Email', 'CERN Access']
        rows = [{'Id': reg.friendly_id, 'First Name': reg.first_name, 'Last Name': reg.last_name, 'Email': reg.email,
                 'CERN Access': self._get_cern_access_flag(reg)}
                for reg in registrations]
        return column_names, rows


class RHExportCERNAccessExcel(RHExportCERNAccessBase):
    def _process(self):
        headers, rows = self._generate_spreadsheet()
        return send_xlsx('CERN_Access.xlsx', headers, rows)


class RHExportCERNAccessCSV(RHExportCERNAccessBase):
    def _process(self):
        headers, rows = self._generate_spreadsheet()
        return send_csv('CERN_Access.csv', headers, rows)
