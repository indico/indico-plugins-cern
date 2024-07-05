// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import PropTypes from 'prop-types';
import React from 'react';
import {Icon, Segment} from 'semantic-ui-react';

import {FinalCheckbox} from 'indico/react/forms';
import {Markdown} from 'indico/react/util';

export default function BookRoomFormExtraFields({room: {confirmationPrompt}, booking, disabled}) {
  if (!confirmationPrompt || booking) {
    return null;
  }
  return (
    <Segment inverted color="orange">
      <h3 style={{marginBottom: '0.5em'}}>
        <Icon name="warning sign" />
        Confirm requirements
      </h3>
      <Markdown targetBlank>{confirmationPrompt}</Markdown>
      <FinalCheckbox
        name="_requirements_confirmed"
        required
        disabled={disabled}
        label="I confirm that I meet the requirements"
      />
    </Segment>
  );
}

BookRoomFormExtraFields.propTypes = {
  room: PropTypes.shape({
    confirmationPrompt: PropTypes.string,
  }).isRequired,
  booking: PropTypes.object,
  disabled: PropTypes.bool.isRequired,
};

BookRoomFormExtraFields.defaultProps = {
  booking: null,
};
