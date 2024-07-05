// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import setup from 'indico/modules/rb/setup';
import {registerPluginComponent} from 'indico/utils/plugins';

import BookRoomFormExtraFields from './components/BookRoomFormExtraFields.jsx';
import overrides from './overrides';
import parametrized from './parametrized';

const PLUGIN_NAME = 'labotel';

setup({...parametrized, ...overrides});
registerPluginComponent(PLUGIN_NAME, 'rb-booking-form-extra-fields', BookRoomFormExtraFields);
