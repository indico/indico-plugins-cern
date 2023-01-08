// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import BootstrapOptions from './components/BootstrapOptions';
import BurotelLanding from './components/BurotelLanding';
import DailyButton from './components/DailyButton';
import DeskInfoBoxes from './components/DeskInfoBoxes';
import DeskRenderer from './components/DeskRenderer';
import ExtraFilters from './components/ExtraFilters';
import RowLabel from './components/RowLabel';

export default {
  'Landing': BurotelLanding,
  'RoomRenderer': DeskRenderer,
  'Landing.bootstrapOptions': BootstrapOptions,
  'RoomFilterBar.extraFilters': ExtraFilters,
  'BookingFilterBar.recurrence': DailyButton,
  'TimelineContent.rowLabel': RowLabel,
  'RoomDetails.infoBoxes': DeskInfoBoxes,
};
