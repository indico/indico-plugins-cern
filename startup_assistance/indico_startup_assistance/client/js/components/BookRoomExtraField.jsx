/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2018 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import React from 'react';
import PropTypes from 'prop-types';
import {Field} from 'react-final-form';

import {Translate} from 'indico/react/i18n';
import {ReduxCheckboxField} from 'indico/react/forms';

import './BookRoomExtraField.module.scss';


export default class BookRoomExtraField extends React.Component {
    static defaultProps = {
        room: PropTypes.object.isRequired,
        disabled: PropTypes.object,
    };

    static defaultProps = {
        disabled: false,
    };

    render() {
        const {room: {notificationForAssistance}, disabled} = this.props;
        if (!notificationForAssistance) {
            return null;
        }

        return (
            <Field name="notificationForAssistance"
                   styleName="assistance-toggle"
                   component={ReduxCheckboxField}
                   componentLabel={Translate.string('Request startup assistance before the booking')}
                   disabled={disabled}
                   toggle />
        );
    }
}
