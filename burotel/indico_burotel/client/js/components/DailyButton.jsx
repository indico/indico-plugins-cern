// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2022 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';
import {Button} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

export default function DailyButton() {
  return (
    <Button primary>
      <Translate>Daily</Translate>
    </Button>
  );
}
