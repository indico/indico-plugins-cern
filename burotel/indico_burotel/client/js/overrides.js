// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2019 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import DeskRenderer from './components/DeskRenderer';
import BootstrapOptions from './components/BootstrapOptions';
import ExtraFilters from './components/ExtraFilters';
import DailyButton from './components/DailyButton';
import BurotelLanding from './components/BurotelLanding';
import RowLabel from './components/RowLabel';
import DeskInfoBoxes from './components/DeskInfoBoxes';

export default {
  'Landing': BurotelLanding,
  'RoomRenderer': DeskRenderer,
  'Landing.bootstrapOptions': BootstrapOptions,
  'RoomFilterBar.extraFilters': ExtraFilters,
  'BookingFilterBar.recurrence': DailyButton,
  'TimelineContent.rowLabel': RowLabel,
  'RoomDetails.infoBoxes': DeskInfoBoxes,
};
