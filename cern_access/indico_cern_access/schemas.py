# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from datetime import date

from marshmallow import ValidationError, fields, post_load, validate, validates_schema

from indico.core.marshmallow import mm
from indico.util.marshmallow import validate_with_message

from indico_cern_access.util import sanitize_license_plate


class RequestAccessSchema(mm.Schema):
    request_cern_access = fields.Bool(load_default=False, data_key='cern_access_request_cern_access')
    birth_date = fields.Date(load_default=None, data_key='cern_access_birth_date',
                             validate=validate_with_message(lambda x: x <= date.today(),
                                                            'The specified date is in the future'))
    nationality = fields.String(load_default='', data_key='cern_access_nationality')
    birth_place = fields.String(load_default='', data_key='cern_access_birth_place')
    by_car = fields.Bool(load_default=False, data_key='cern_access_by_car')
    license_plate = fields.String(data_key='cern_access_license_plate', load_default=None)

    @validates_schema
    def validate_everything(self, data, **kwargs):
        # this ugly mess is needed since we can't skip fields conditionally...
        if not data['request_cern_access']:
            return
        required_fields = {'birth_date', 'nationality', 'birth_place'}
        if data['by_car']:
            required_fields.add('license_plate')
        errors = {}
        for field in required_fields:
            if not data[field]:
                errors[self.fields[field].data_key] = ['This field is required.']
        if data['by_car'] and data['license_plate']:
            try:
                validate.And(
                    validate.Length(min=3),
                    validate.Regexp(r'^[0-9A-Za-z]+([- ][ ]*[0-9A-Za-z]+)*$')
                )(data['license_plate'])
            except ValidationError as exc:
                errors.setdefault(self.fields['license_plate'].data_key, []).extend(exc.messages)
        if errors:
            raise ValidationError(errors)

    @post_load
    def _cleanup(self, data, **kwargs):
        # remove data we don't use
        if not data['request_cern_access']:
            data['birth_date'] = None
            data['nationality'] = data['birth_place'] = ''
            data['by_car'] = False
            data['license_plate'] = None
        elif not data['by_car']:
            data['license_plate'] = None
        # normalize license plate string
        if data['license_plate']:
            data['license_plate'] = sanitize_license_plate(data['license_plate'])
        return data
