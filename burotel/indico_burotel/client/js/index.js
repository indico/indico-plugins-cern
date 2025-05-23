// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import setup from 'indico/modules/rb/setup';

import overrides from './overrides';
import parametrized from './parametrized';
import reducers from './reducers';

setup({...parametrized, ...overrides}, reducers);
