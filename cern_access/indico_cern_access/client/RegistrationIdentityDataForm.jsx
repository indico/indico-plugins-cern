// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import _ from 'lodash';
import moment from 'moment';
import PropTypes from 'prop-types';
import React from 'react';
import {Dropdown, Form, Input} from 'semantic-ui-react';

import {FinalSingleDatePicker, SingleDatePicker} from 'indico/react/components';
import {
  FieldCondition,
  FinalCheckbox,
  FinalDropdown,
  FinalField,
  FinalInput,
} from 'indico/react/forms';
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
  const handleOnChange = (id, field, newFieldValue) => {
    const newValueEntry = {...value[id]};
    const newValue = {...value};
    newValueEntry[field] = newFieldValue;
    newValue[id] = newValueEntry;
    onChange(newValue);
  };
  const makeOnChange = (id, field) => (evt, {value: v}) => handleOnChange(id, field, v);

  return (
    <table styleName="accompanying-persons-table">
      <thead>
        <tr>
          <th />
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
                isOutsideRange={v => v.isAfter()}
                placeholder={moment.localeData().longDateFormat('L')}
                date={toMoment(value[id]?.birth_date, 'YYYY-MM-DD')}
                onDateChange={date => handleOnChange(id, 'birth_date', serializeDate(date))}
                enableOutsideDays
                required
                yearsBefore={100}
                yearsAfter={0}
              />
            </td>
            <td>
              <Dropdown
                name="nationality"
                options={countryOptions}
                placeholder={Translate.string('Select a country')}
                value={value[id]?.nationality}
                onChange={makeOnChange(id, 'nationality')}
                required
                search
                selection
              />
            </td>
            <td>
              <Input
                name="birth_place"
                value={value[id]?.birth_place || ''}
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
  value: PropTypes.objectOf(
    PropTypes.shape({
      id: PropTypes.string,
      birth_date: PropTypes.string,
      nationality: PropTypes.string,
      birth_place: PropTypes.string,
    })
  ).isRequired,
  countryOptions: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      value: PropTypes.string.isRequired,
      text: PropTypes.string.isRequired,
    })
  ).isRequired,
  accompanyingPersons: PropTypes.arrayOf(PropTypes.shape(accompanyingPersonShape)).isRequired,
};

export default function RegistrationIdentityDataForm({
  countries,
  accompanying,
  accompanyingPersons,
}) {
  const countryOptions = countries.map(([k, v]) => ({
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
        yearsBefore={100}
        yearsAfter={0}
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
              validate={value => {
                if (
                  accompanyingPersons.some(({id}) => {
                    const personData = value[id];
                    return (
                      !personData ||
                      !personData.birth_place ||
                      !personData.birth_date ||
                      !personData.nationality
                    );
                  })
                ) {
                  return Translate.string('Data for accompanying persons must be provided.');
                }
              }}
              required
            />
          ) : (
            <Translate>No accompanying persons were added yet.</Translate>
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
  countries: PropTypes.array.isRequired,
  accompanying: PropTypes.bool.isRequired,
  accompanyingPersons: PropTypes.arrayOf(PropTypes.shape(accompanyingPersonShape)).isRequired,
};
