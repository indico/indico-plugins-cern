// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import saveURL from 'indico-url:plugin_cern_access.access_identity_data';
import saveURLManagement from 'indico-url:plugin_cern_access.enter_identity_data';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import ReactDOM from 'react-dom';
import {Form as FinalForm} from 'react-final-form';
import {Form} from 'semantic-ui-react';

import {FinalSubmitButton, handleSubmitError} from 'indico/react/forms';
import {indicoAxios} from 'indico/utils/axios';

import {Translate} from './i18n';
import RegistrationIdentityDataForm from './RegistrationIdentityDataForm';

function EnterPersonalDataForm({registration, isManagement, ...rest}) {
  const handleSubmit = async data => {
    try {
      await indicoAxios.put(
        isManagement ? saveURLManagement(registration) : saveURL(registration),
        {...data, cern_access_request_cern_access: true}
      );
    } catch (e) {
      return handleSubmitError(e);
    }
    location.reload();
    // never finish submitting to avoid fields being re-enabled
    await new Promise(() => {});
  };

  const initialValues = {
    cern_access_birth_date: '',
    cern_access_nationality: '',
    cern_access_birth_place: null,
    cern_access_accompanying_persons: {},
    cern_access_by_car: false,
    cern_access_license_plate: '',
  };

  return (
    <FinalForm
      onSubmit={handleSubmit}
      initialValues={initialValues}
      initialValuesEqual={_.isEqual}
      subscription={{}}
    >
      {fprops => (
        <Form onSubmit={fprops.handleSubmit}>
          <RegistrationIdentityDataForm {...rest} />
          <FinalSubmitButton label={Translate.string('Save')} className="submit-button" />
        </Form>
      )}
    </FinalForm>
  );
}

EnterPersonalDataForm.propTypes = {
  registration: PropTypes.object.isRequired,
  isManagement: PropTypes.bool.isRequired,
};

window.setupEnterPersonalDataForm = function setupEnterPersonalDataForm({
  registration,
  isManagement,
  countries,
  accompanying,
  accompanyingPersons,
}) {
  const container = document.querySelector('#registration-identity-data-form-container');
  $(container)
    .closest('.ui-dialog-content')
    .css('overflow', 'inherit');
  $(container)
    .closest('.exclusivePopup')
    .css('overflow', 'inherit');

  ReactDOM.render(
    <EnterPersonalDataForm
      registration={registration}
      isManagement={isManagement}
      countries={countries}
      accompanying={accompanying}
      accompanyingPersons={accompanyingPersons}
    />,
    container
  );
};
