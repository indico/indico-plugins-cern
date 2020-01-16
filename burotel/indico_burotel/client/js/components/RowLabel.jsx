// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2020 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';
import PropTypes from 'prop-types';

import {Translate} from 'indico/react/i18n';

import {TimelineRowLabel} from 'indico/modules/rb/common/timeline/DailyTimelineContent';


const RowLabel = ({room, ...props}) => (
    <TimelineRowLabel {...props}
                      gutter={room.isLongTerm}
                      gutterTooltip={Translate.string('Long term')} />
);

RowLabel.propTypes = {
    room: PropTypes.object.isRequired,
};

export default RowLabel;
