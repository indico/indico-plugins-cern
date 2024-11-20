// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import BootstrapOptions from './components/BootstrapOptions';
import LabotelLanding from './components/LabotelLanding';
import ExtraFilters from './components/ExtraFilters';
import LabRenderer from './components/LabRenderer';

export default {
  'Landing': LabotelLanding,
  'Landing.bootstrapOptions': BootstrapOptions,
  'RoomFilterBar.extraFilters': ExtraFilters,
  'RoomRenderer': LabRenderer,
};
