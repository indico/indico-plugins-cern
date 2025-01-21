// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import divisionsURL from 'indico-url:plugin_labotel.divisions';

import PropTypes from 'prop-types';
import React from 'react';
import {useSelector} from 'react-redux';
import {Form, Button, Checkbox} from 'semantic-ui-react';

import {selectors as userSelectors} from 'indico/modules/rb/common/user';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';

export default function BootstrapOptions({options: {division}, setOptions}) {
  const userHasFavorites = useSelector(userSelectors.hasFavoriteRooms);
  const {data: divisions} = useIndicoAxios(divisionsURL());

  const handleDivisionClick = async newDivision => {
    setOptions({division: newDivision});
  };

  return (
    <>
      {userHasFavorites && (
        <Form.Field>
          <Checkbox
            label={Translate.string('Search only my favorites')}
            onClick={(evt, {checked}) => setOptions({onlyFavorites: checked})}
          />
        </Form.Field>
      )}
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
    </>
  );
}

BootstrapOptions.propTypes = {
  setOptions: PropTypes.func.isRequired,
  options: PropTypes.object.isRequired,
};
