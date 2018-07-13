# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import jsonify, redirect, render_template, request
from flask_pluginengine import current_plugin, render_plugin_template
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from indico.core.db import db
from indico.core.errors import NoReportError, UserValueError
from indico.modules.events.registration.controllers.display import RHRegistrationFormRegistrationBase
from indico.modules.events.registration.controllers.management import RHManageRegistrationBase
from indico.modules.events.registration.controllers.management.reglists import RHRegistrationsActionBase
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.requests.controllers import RHRequestsEventRequestDetailsBase
from indico.util.date_time import now_utc
from indico.util.placeholders import replace_placeholders
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.web.flask.templating import get_template_module
from indico.web.flask.util import url_for
from indico.web.util import jsonify_data, jsonify_template

from indico_cern_access import _
from indico_cern_access.forms import AccessIdentityDataForm, GrantAccessEmailForm
from indico_cern_access.util import get_access_dates, get_last_request, grant_access, revoke_access, send_ticket
from indico_cern_access.views import WPAccessRequestDetails


class RHRegistrationGrantCERNAccess(RHRegistrationsActionBase):
    """Grant CERN access to registrants."""

    def _process(self):
        tpl = get_template_module('cern_access:emails/identity_data_form_email_default.html', event=self.event)
        default_subject = current_plugin.event_settings.get(self.event, 'email_subject') or tpl.get_subject()
        default_body = current_plugin.event_settings.get(self.event, 'email_body') or tpl.get_html_body()
        registration_ids = request.form.getlist('registration_id')
        form = GrantAccessEmailForm(subject=default_subject, body=default_body, regform=self.regform,
                                    registration_id=registration_ids)
        if form.validate_on_submit():
            if form.save_default.data:
                current_plugin.event_settings.set(self.event, 'email_subject', form.subject.data)
                current_plugin.event_settings.set(self.event, 'email_body', form.body.data)
            grant_access(self.registrations, self.regform, form.subject.data, form.body.data, form.from_address.data)
            return jsonify_data(**self.list_generator.render_list())
        return jsonify_template('cern_access:grant_access.html', form=form, regform=self.regform)


class RHRegistrationRevokeCERNAccess(RHRegistrationsActionBase):
    """Revoke CERN access from registrants."""

    def _process(self):
        revoke_access(self.registrations)
        return jsonify_data(**self.list_generator.render_list())


class RHRegistrationPreviewCERNAccessEmail(RHRegistrationsActionBase):
    """Preview the email that will be sent to registrants"""

    def _process(self):
        if not self.registrations:
            raise NoReportError.wrap_exc(BadRequest(_("The selected registrants have been removed.")))
        registration = self.registrations[0]
        email_body = replace_placeholders('cern-access-email', request.form['body'], regform=self.regform,
                                          registration=registration)
        email_subject = replace_placeholders('cern-access-email', request.form['subject'], regform=self.regform,
                                             registration=registration)
        tpl = get_template_module('cern_access:emails/identity_data_form_email.html', registration=registration,
                                  email_subject=email_subject, email_body=email_body)
        html = render_template('events/registration/management/email_preview.html', subject=tpl.get_subject(),
                               body=tpl.get_body())
        return jsonify(html=html)


class RHRegistrationAccessIdentityData(RHRegistrationFormRegistrationBase):
    def _process_args(self):
        RHRegistrationFormRegistrationBase._process_args(self)
        self.cern_access_request = get_last_request(self.event)
        if not self.cern_access_request:
            raise NotFound

    def _check_access(self):
        # no access restrictions for this page
        pass

    def _process(self):
        start_dt, end_dt = get_access_dates(self.cern_access_request)
        expired = now_utc() > end_dt
        form = AccessIdentityDataForm()
        access_request = self.registration.cern_access_request
        if access_request is not None and not access_request.has_identity_info and form.validate_on_submit():
            if expired:
                raise Forbidden
            form.populate_obj(access_request)
            db.session.flush()
            send_ticket(self.registration)
            return redirect(url_for('.access_identity_data', self.registration.locator.uuid))

        return WPAccessRequestDetails.render_template('identity_data_form.html', self.event, form=form,
                                                      access_request=access_request, start_dt=start_dt, end_dt=end_dt,
                                                      expired=expired)


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
