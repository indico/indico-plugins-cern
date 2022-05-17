// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2022 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import _ from 'lodash';
import moment from 'moment';
import PropTypes from 'prop-types';
import React, {useMemo} from 'react';
import {Dropdown, Form, Input} from 'semantic-ui-react';

import {FinalSingleDatePicker, SingleDatePicker} from 'indico/react/components';
import {FieldCondition, FinalCheckbox, FinalDropdown, FinalField, FinalInput} from 'indico/react/forms';
import {serializeDate, toMoment} from 'indico/utils/date';

import {Translate} from './i18n';

import './RegistrationIdentityDataForm.module.scss';

// eslint-disable-next-line react/prop-types
function CERNAccessItem({as: InputComponent, title, required, ...inputProps}) {
  return (
    <div styleName="form-item">
      <div styleName="content">
        <Form.Field required={required} styleName="field">
          {title && <label>{title}</label>}
          <InputComponent required={required} {...inputProps} />
        </Form.Field>
      </div>
    </div>
  );
}

const isoToFlag = country =>
  String.fromCodePoint(...country.split('').map(c => c.charCodeAt() + 0x1f1a5));

const accompanyingPersonShape = {
  id: PropTypes.string,
  firstName: PropTypes.string,
  lastName: PropTypes.string,
};

function AccompanyingPersonsComponent({onChange, value, countryOptions, accompanyingPersons}) {
  const valueById = useMemo(() => (value ? Object.assign(
    {},
    ...value.map(({id, birth_date, nationality, birth_place}) => ({[id]: {birth_date, nationality, birth_place}}))
  ) : {}), [value]);

  const handleOnChange = (id, field, newValue) => {
    if (id in valueById) {
      const newValueEntry = {id, ...valueById[id]};
      newValueEntry[field] = newValue;
      onChange([...value.filter(v => v.id !== id), newValueEntry]);
    } else {
      onChange([...value, {id, [field]: newValue}]);
    }
  }
  const makeOnChange = (id, field) => (evt, {value: v}) => handleOnChange(id, field, v);

  return (
    <table styleName="accompanying-persons-table">
      <thead>
        <tr>
          <th></th>
          <th style={{width: '15em'}}>
            <Translate>Birth date</Translate>
          </th>
          <th style={{width: '15em'}}>
            <Translate>Country of birth</Translate>
          </th>
          <th style={{width: '15em'}}>
            <Translate>Place of birth</Translate>
          </th>
        </tr>
      </thead>
      <tbody>
        {accompanyingPersons.map(({id, firstName, lastName}) => (
          <tr key={id}>
            <td>
              {firstName} {lastName}
            </td>
            <td>
              <SingleDatePicker
                name="birth_date"
                isOutsideRange={value => value.isAfter()}
                placeholder={moment.localeData().longDateFormat('L')}
                date={toMoment(valueById[id]?.birth_date, 'YYYY-MM-DD')}
                onDateChange={date => handleOnChange(id, 'birth_date', serializeDate(date))}
                enableOutsideDays
                required
              />
            </td>
            <td>
              <Dropdown
                name="nationality"
                options={countryOptions}
                placeholder={Translate.string('Select a country')}
                value={valueById[id]?.nationality}
                onChange={makeOnChange(id, 'nationality')}
                required
                search
                selection
              />
            </td>
            <td>
              <Input
                name="birth_place"
                value={valueById[id]?.birth_place || ''}
                onChange={makeOnChange(id, 'birth_place')}
                required
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

AccompanyingPersonsComponent.propTypes = {
  onChange: PropTypes.func.isRequired,
  value: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string,
    birth_date: PropTypes.string,
    nationality: PropTypes.string,
    birth_place: PropTypes.string,
  })).isRequired,
  countryOptions: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string.isRequired,
    value: PropTypes.string.isRequired,
    text: PropTypes.string.isRequired,
  })).isRequired,
  accompanyingPersons: PropTypes.arrayOf(PropTypes.shape(accompanyingPersonShape)).isRequired,
};

export default function RegistrationIdentityDataForm({countries, accompanying, accompanyingPersons}) {
  const countryOptions = Object.entries(countries).map(([k, v]) => ({
    key: k,
    value: k,
    text: `${isoToFlag(k)} ${v}`,
  }));

  return (
    <Form as="div" className="i-box-content">
      <CERNAccessItem
        name="cern_access_birth_date"
        title={Translate.string('Birth date')}
        as={FinalSingleDatePicker}
        required
        isOutsideRange={value => value.isAfter()}
        enableOutsideDays
        placeholder={moment.localeData().longDateFormat('L')}
      />
      <CERNAccessItem
        name="cern_access_nationality"
        title={Translate.string('Country of birth')}
        placeholder={Translate.string('Select a country')}
        as={FinalDropdown}
        options={countryOptions}
        required
        search
        selection
      />
      <CERNAccessItem
        name="cern_access_birth_place"
        title={Translate.string('Place of birth')}
        as={FinalInput}
        required
      />
      {accompanying && (
        <>
          <h3 className="vehicle-section-title">
            <i className="user-icon" />
            <Translate>Accompanying Persons</Translate>
          </h3>
          {accompanyingPersons.length > 0 ? (
            <FinalField
              name="cern_access_accompanying_persons"
              component={AccompanyingPersonsComponent}
              countryOptions={countryOptions}
              accompanyingPersons={accompanyingPersons}
              isEqual={_.isEqual}
              required
            />
          ) : (
            <Translate>
              No accompanying persons were added yet.
            </Translate>
          )}
        </>
      )}
      <h3 className="vehicle-section-title">
        <i className="car-icon" />
        <Translate>Vehicle Registration</Translate>
      </h3>
      <CERNAccessItem
        name="cern_access_by_car"
        title=""
        label={Translate.string("I'm coming by car")}
        as={FinalCheckbox}
      />
      <FieldCondition when="cern_access_by_car" is>
        <CERNAccessItem
          name="cern_access_license_plate"
          title={Translate.string('License plate')}
          as={FinalInput}
          required
          nullIfEmpty
          validate={val => {
            if (!val) {
              return undefined;
            } else if (val.length < 3) {
              return Translate.string('Must be at least 3 characters');
            } else if (!val.match(/^[0-9A-Za-z]+([- ][ ]*[0-9A-Za-z]+)*$/)) {
              return Translate.string(
                'Wrong format. Only letters and numbers separated by dashes (-) or spaces allowed'
              );
            }
          }}
        />
      </FieldCondition>
    </Form>
  );
}

RegistrationIdentityDataForm.propTypes = {
  countries: PropTypes.object.isRequired,
  accompanying: PropTypes.bool.isRequired,
  accompanyingPersons: PropTypes.arrayOf(PropTypes.shape(accompanyingPersonShape)).isRequired,
};
