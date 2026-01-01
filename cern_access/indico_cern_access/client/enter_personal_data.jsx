// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

/* global updateHtml:false, handleFlashes:false */

import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import ReactDOM from 'react-dom';
import {Form as FinalForm} from 'react-final-form';
import {Form, Message} from 'semantic-ui-react';

import {FinalSubmitButton, handleSubmitError} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {injectModal} from 'indico/react/util';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

import {Translate} from './i18n';
import RegistrationIdentityDataForm from './RegistrationIdentityDataForm';

const initialValues = {
  cern_access_birth_date: '',
  cern_access_nationality: '',
  cern_access_birth_place: null,
  cern_access_accompanying_persons: {},
  cern_access_by_car: false,
  cern_access_license_plate: '',
};

function EnterPersonalDataForm({url, ...rest}) {
  const handleSubmit = async data => {
    try {
      await indicoAxios.put(url, {...data, cern_access_request_cern_access: true});
    } catch (e) {
      return handleSubmitError(e);
    }
    location.reload();
    // never finish submitting to avoid fields being re-enabled
    await new Promise(() => {});
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
  url: PropTypes.string.isRequired,
};

window.setupEnterPersonalDataForm = function setupEnterPersonalDataForm({
  url,
  countries,
  accompanying,
  accompanyingPersons,
}) {
  const container = document.querySelector('#registration-identity-data-form-container');
  ReactDOM.render(
    <EnterPersonalDataForm
      url={url}
      countries={countries}
      accompanying={accompanying}
      accompanyingPersons={accompanyingPersons}
    />,
    container
  );
};

function EnterPersonalDataDialog({url, title, callback, ...rest}) {
  const handleSubmit = async data => {
    let resp;
    try {
      resp = await indicoAxios.put(url, {...data, cern_access_request_cern_access: true});
    } catch (e) {
      return handleSubmitError(e);
    }
    callback(resp.data);
  };

  return (
    <FinalModalForm
      id="enter-cern-data-form"
      onSubmit={handleSubmit}
      onClose={() => callback(null)}
      initialValues={initialValues}
      initialValuesEqual={_.isEqual}
      header={title}
      size="large"
    >
      <Message info>
        <Translate as="p">
          CERN's Security Policy requires external users entering the CERN site to provide the
          following additional data. This data will not be shared with you and will only be revealed
          upon request from CERN's Site Surveillance service.
        </Translate>
        <Translate as="p">
          Note that you usually do not need to fill out this form! When you requested CERN access
          for this user, an email with a link to this form has been sent to them. You may however
          enter the data on behalf of the user; in this case it is your responsibility to ensure
          that the data is correct and the user is aware that it will be stored in our database
          temporarily.
        </Translate>
        <Translate as="p">
          After entering the data, the ticket will be immediately sent to the user, if sending
          tickets by email is enabled.
        </Translate>
      </Message>
      <RegistrationIdentityDataForm {...rest} />
    </FinalModalForm>
  );
}

EnterPersonalDataDialog.propTypes = {
  url: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  callback: PropTypes.func.isRequired,
};

async function showCERNDataDialog(url, title, selector) {
  let data;
  try {
    data = (await indicoAxios.get(url)).data;
  } catch (error) {
    handleAxiosError(error);
    return;
  }
  injectModal(resolve => (
    <EnterPersonalDataDialog
      url={url}
      title={title}
      callback={resp => {
        if (resp) {
          const col = document.querySelector(selector);
          updateHtml(col, resp, true, false);
          handleFlashes(resp);
        }
        resolve();
      }}
      // data for the RegistrationIdentityDataForm
      countries={data.countries}
      accompanying={data.accompanying}
      accompanyingPersons={data.accompanying_persons}
    />
  ));
}

document.addEventListener('DOMContentLoaded', () => {
  const managementRegList = document.querySelector('.registrations');
  if (managementRegList) {
    managementRegList.addEventListener('click', evt => {
      const elem = evt.target;
      if (elem.matches('.js-enter-cern-data')) {
        evt.stopPropagation();
        evt.preventDefault();
        showCERNDataDialog(elem.dataset.href, elem.dataset.title, elem.dataset.update);
      }
    });
  }
});
