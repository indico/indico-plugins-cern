// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import defaultDivisionURL from 'indico-url:plugin_labotel.user_division';

import PropTypes from 'prop-types';
import React from 'react';
import {Button} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

export const DIVISIONS = ['Laser', 'Clean Room', 'DSF/QART'];

export default class BootstrapOptions extends React.Component {
  static propTypes = {
    setOptions: PropTypes.func.isRequired,
    options: PropTypes.object.isRequired,
  };

  handleDivisionClick = async division => {
    const {setOptions} = this.props;
    setOptions({division});
    try {
      await indicoAxios.post(defaultDivisionURL(), {value: division});
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
        {DIVISIONS.map(div => (
          <Button
            key={div}
            onClick={() => this.handleDivisionClick(div)}
            type="button"
            primary={division === div}
          >
            {div}
          </Button>
        ))}
        <Button
          key="other"
          onClick={() => this.handleDivisionClick(null)}
          type="button"
          primary={!division}
        >
          <Translate>All</Translate>
        </Button>
      </Button.Group>
    );
  }
}
