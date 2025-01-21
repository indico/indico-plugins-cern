// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import divisionsURL from 'indico-url:plugin_labotel.divisions';
import defaultDivisionURL from 'indico-url:plugin_labotel.user_division';

import PropTypes from 'prop-types';
import React from 'react';
import {Button} from 'semantic-ui-react';

import {useIndicoAxios} from 'indico/react/hooks';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

export default function BootstrapOptions({options: {division}, setOptions}) {
  const {data: divisions} = useIndicoAxios(divisionsURL());

  const handleDivisionClick = async newDivision => {
    setOptions({division: newDivision});
    try {
      await indicoAxios.post(defaultDivisionURL(), {value: newDivision});
    } catch (error) {
      handleAxiosError(error);
    }
  };

  return (
    <Button.Group style={{marginBottom: 10}}>
      {divisions?.map(div => (
        <Button
          key={div}
          onClick={() => handleDivisionClick(division === div ? null : div)}
          type="button"
          toggle
          active={division === div}
        >
          {div}
        </Button>
      ))}
    </Button.Group>
  );
}

BootstrapOptions.propTypes = {
  setOptions: PropTypes.func.isRequired,
  options: PropTypes.object.isRequired,
};
