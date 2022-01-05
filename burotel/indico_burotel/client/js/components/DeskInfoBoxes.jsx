// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2022 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';
import PropTypes from 'prop-types';
import {Icon, Message} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import './DeskInfoBoxes.module.scss';


const DeskInfoBoxes = ({children, room}) => (
    <>
        {room.isLongTerm && (
            <Message styleName="message-icon" icon>
                <Icon name="stopwatch" />
                <Translate>Long term desk</Translate>
            </Message>
        )}
        {children}
    </>
);

DeskInfoBoxes.propTypes = {
    children: PropTypes.node.isRequired,
    room: PropTypes.object.isRequired,
};

export default DeskInfoBoxes;
