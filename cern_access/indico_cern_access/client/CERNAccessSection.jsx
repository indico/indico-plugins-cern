// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import createDecorator from 'final-form-calculate';
import _ from 'lodash';
import moment from 'moment';
import React, {useMemo} from 'react';
import {useFormState} from 'react-final-form';
import {useSelector} from 'react-redux';
import {createSelector} from 'reselect';

import {FinalCheckbox, FieldCondition} from 'indico/react/forms';
import {toMoment} from 'indico/utils/date';

import {Translate, Param} from './i18n';
import RegistrationIdentityDataForm from './RegistrationIdentityDataForm';

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

const getStaticRegformData = createSelector(
  state => state.staticData.extraData.cernAccess,
  data => (data ? JSON.parse(data) : null)
);

export default function CERNAccessSection() {
  const data = useSelector(getStaticRegformData);
  if (!data) {
    return null;
  }
  const {countries, start, end, preselected, required, accompanying} = data;
  const items = useSelector(state => state.items);
  const formState = useFormState();
  const canHaveAccompanyingPersons =
    accompanying && Object.values(items).filter(f => f.inputType === 'accompanying_persons').length > 0;
  const accompanyingPersons = useMemo(
    () => _.flatten(Object.values(items).filter(f => f.inputType === 'accompanying_persons').map(f => formState.values[f.htmlName])),
    [formState]
  );

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
      <RegistrationIdentityDataForm
        countries={countries}
        accompanying={canHaveAccompanyingPersons}
        accompanyingPersons={accompanyingPersons}
      />
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
            {canHaveAccompanyingPersons ? (
              <Translate>
                In case you or an accompanying person do not have a valid CERN badge, you can request
                temporary CERN site access here.
              </Translate>
            ) : (
              <Translate>
                In case you do not have a valid CERN badge, you can request temporary CERN site access
                here.
              </Translate>
            )}
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
            cern_access_accompanying_persons: [],
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
