// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import defaultExperimentURL from 'indico-url:plugin_labotel.user_experiment';

import PropTypes from 'prop-types';
import React from 'react';
import {Button} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

export const EXPERIMENTS = ['ATLAS', 'CMS', 'ALICE', 'LHCb', 'HSE'];

export default class BootstrapOptions extends React.Component {
  static propTypes = {
    setOptions: PropTypes.func.isRequired,
    options: PropTypes.object.isRequired,
  };

  handleExperimentClick = async experiment => {
    const {setOptions} = this.props;
    setOptions({division: experiment});
    try {
      await indicoAxios.post(defaultExperimentURL(), {value: experiment});
    } catch (error) {
      handleAxiosError(error);
    }
  };

  render() {
    const {
      options: {division},
    } = this.props;

    return (
      <Button.Group style={{marginBottom: 10}}>
        {EXPERIMENTS.map(experiment => (
          <Button
            key={experiment}
            onClick={() => this.handleExperimentClick(experiment)}
            type="button"
            primary={division === experiment}
          >
            {experiment}
          </Button>
        ))}
        <Button
          key="other"
          onClick={() => this.handleExperimentClick(null)}
          type="button"
          primary={!division}
        >
          <Translate>All</Translate>
        </Button>
      </Button.Group>
    );
  }
}
