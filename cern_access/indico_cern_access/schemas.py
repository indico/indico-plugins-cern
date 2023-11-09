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

from indico_cern_access.util import get_accompanying_persons, get_last_request, sanitize_license_plate


class AccompanyingPersonAccessSchema(mm.Schema):
    birth_date = fields.Date(required=True,
                             validate=validate_with_message(lambda x: x <= date.today(),
                                                            'The specified date is in the future'))
    nationality = fields.String(required=True)
    birth_place = fields.String(required=True)


class RequestAccessSchema(mm.Schema):
    class Meta:
        rh_context = ('registration', 'accompanying_persons')

    request_cern_access = fields.Bool(load_default=False, data_key='cern_access_request_cern_access')
    birth_date = fields.Date(load_default=None, data_key='cern_access_birth_date',
                             validate=validate_with_message(lambda x: x <= date.today(),
                                                            'The specified date is in the future'))
    nationality = fields.String(load_default='', data_key='cern_access_nationality')
    birth_place = fields.String(load_default='', data_key='cern_access_birth_place')
    accompanying_persons = fields.Dict(keys=fields.String(), values=fields.Nested(AccompanyingPersonAccessSchema),
                                       load_default={}, data_key='cern_access_accompanying_persons')
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
        if reg := self.context.get('registration'):
            accompanying_persons = get_accompanying_persons(reg, get_last_request(reg.event))[1]
        else:
            accompanying_persons = self.context['accompanying_persons']
        if any(p['id'] not in data['accompanying_persons'] for p in accompanying_persons):
            errors[self.fields['accompanying_persons'].data_key] = ['Missing data for accompanying person']
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
            data['accompanying_persons'] = {}
        elif not data['by_car']:
            data['license_plate'] = None
        # normalize license plate string
        if data['license_plate']:
            data['license_plate'] = sanitize_license_plate(data['license_plate'])
        return data
