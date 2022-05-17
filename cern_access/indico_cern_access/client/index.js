// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {registerPluginComponent, registerPluginObject} from 'indico/utils/plugins';

import CERNAccessSection, {formDecorator} from './CERNAccessSection';
import './EnterPersonalDataForm';
import './main.scss';

const PLUGIN_NAME = 'cern_access';

registerPluginComponent(PLUGIN_NAME, 'regformAfterSections', CERNAccessSection);
registerPluginObject(PLUGIN_NAME, 'regformFormDecorators', formDecorator);
