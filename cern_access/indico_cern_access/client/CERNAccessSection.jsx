// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2022 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import createDecorator from 'final-form-calculate';
import moment from 'moment';
import React from 'react';
import {useSelector} from 'react-redux';
import {createSelector} from 'reselect';
import {Form} from 'semantic-ui-react';

import {FinalSingleDatePicker} from 'indico/react/components';
import {FinalCheckbox, FinalDropdown, FinalInput, FieldCondition} from 'indico/react/forms';
import {toMoment} from 'indico/utils/date';

import {Translate, Param} from './i18n';

import './CERNAccessSection.module.scss';

const renderAccessDates = (start, end) => {
  const startDT = toMoment(start, moment.HTML5_FMT.DATETIME_LOCAL);
  const endDT = toMoment(end, moment.HTML5_FMT.DATETIME_LOCAL);
  if (startDT.isSame(endDT, 'day')) {
    const date = startDT.format('LL');
    const startTime = startDT.format('LT');
    const endTime = endDT.format('LT');
    return `${date} (${startTime} - ${endTime})`;
  } else {
    const startDateTime = startDT.format('LL (LT)');
    const endDateTime = endDT.format('LL (LT)');
    return `${startDateTime} - ${endDateTime}`;
  }
};

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

const getStaticRegformData = createSelector(
  state => state.staticData.extraData.cernAccess,
  data => (data ? JSON.parse(data) : null)
);

const isoToFlag = country =>
  String.fromCodePoint(...country.split('').map(c => c.charCodeAt() + 0x1f1a5));

export default function CERNAccessSection() {
  const data = useSelector(getStaticRegformData);
  if (!data) {
    return null;
  }
  const {countries, start, end, preselected, required} = data;
  const countryOptions = Object.entries(countries).map(([k, v]) => ({
    key: k,
    value: k,
    text: `${isoToFlag(k)} ${v}`,
  }));

  const dates = renderAccessDates(start, end);
  const form = (
    <div className="i-box" style={required ? {marginTop: '15px'} : {}}>
      <div className="i-box-header site-access-box-header">
        <div className="i-box-title">
          <Translate>Request access to the CERN site</Translate>
        </div>
        <div className="policy-text-box">
          <Translate>
            CERN's Security Policy requires you to provide the following additional data. The
            contents of this form will not be shared with the event organizers and will only be
            revealed upon request from CERN's Site Surveillance service.
          </Translate>
          <br />
          <br />
          <Translate>
            Once you have provided this data, you will be able to get a ticket which grants you
            access to the CERN site during this period: <Param name="dates" value={dates} />
          </Translate>
        </div>
      </div>
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
        <h2 className="vehicle-section-title">
          <i className="car-icon" />
          <Translate>Vehicle Registration</Translate>
        </h2>
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
    </div>
  );

  if (required) {
    return form;
  }

  const toggle = (
    <div className="action-box highlight" style={{marginTop: '15px'}}>
      <div className="section">
        <div className="icon icon-location" />
        <div className="text">
          <div className="label">
            <Translate>Request access to the CERN site</Translate>
          </div>
          <div className="text">
            <Translate>
              In case you do not have a valid CERN badge, you can request temporary CERN site access
              here.
            </Translate>
          </div>
        </div>
        <div className="toolbar">
          <FinalCheckbox
            name="cern_access_request_cern_access"
            label=""
            toggle
            initialValue={preselected}
          />
        </div>
      </div>
    </div>
  );

  return (
    <>
      {toggle}
      <FieldCondition when="cern_access_request_cern_access" is>
        {form}
      </FieldCondition>
    </>
  );
}

export const formDecorator = createDecorator(
  {
    field: 'cern_access_request_cern_access',
    updates: enabled => {
      return enabled
        ? {}
        : {
            cern_access_birth_date: null,
            cern_access_nationality: '',
            cern_access_birth_place: '',
            cern_access_by_car: false,
            cern_access_license_plate: null,
          };
    },
  },
  {
    field: 'cern_access_by_car',
    updates: enabled => {
      return enabled
        ? {}
        : {
            cern_access_license_plate: null,
          };
    },
  }
);
