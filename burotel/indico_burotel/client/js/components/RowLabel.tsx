// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';

import {TimelineRowLabel} from 'indico/modules/rb/common/timeline/DailyTimelineContent';
import {Translate} from 'indico/react/i18n';

interface Room {
  isLongTerm: boolean;
}

interface RowLabelPropTypes {
  room: Room;
  label: string;
}

function RowLabel({room, ...props}: RowLabelPropTypes) {
  return (
    <TimelineRowLabel
      {...props}
      gutter={room.isLongTerm}
      gutterTooltip={Translate.string('Long term')}
    />
  );
}

export default RowLabel;
