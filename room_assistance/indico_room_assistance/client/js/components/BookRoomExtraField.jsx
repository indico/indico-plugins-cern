/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2019 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import fetchRoomsWithAssistanceURL from 'indico-url:plugin_room_assistance.rooms';
import React from 'react';
import PropTypes from 'prop-types';
import {TextArea} from 'semantic-ui-react';
import {Field} from 'react-final-form';

import {Translate} from 'indico/react/i18n';
import {ReduxCheckboxField, ReduxFormField, formatters, validators as v} from 'indico/react/forms';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

import './BookRoomExtraField.module.scss';


async function getListOfRoomsWithAssistance() {
    let response;
    try {
        response = await indicoAxios.get(fetchRoomsWithAssistanceURL());
    } catch (error) {
        handleAxiosError(error);
        return;
    }
    return response.data;
}


export default class BookRoomExtraField extends React.Component {
    static defaultProps = {
        room: PropTypes.object.isRequired,
        disabled: PropTypes.object,
        form: PropTypes.object.isRequired,
    };

    static defaultProps = {
        disabled: false,
    };

    state = {
        roomsWithAssistance: [],
    };

    async componentDidMount() {
        const roomsWithAssistance = await getListOfRoomsWithAssistance();
        this.setState({roomsWithAssistance});
    }

    render() {
        const {room: {id}, disabled, form} = this.props;
        const {roomsWithAssistance} = this.state;

        if (!roomsWithAssistance.includes(id)) {
            return null;
        }

        const assistanceRequestReasonField = (
            <Field name="assistanceReason"
                   component={ReduxFormField}
                   as={TextArea}
                   disabled={disabled}
                   reactFinalForm={form}
                   validate={v.required}
                   format={formatters.trim}
                   placeholder={Translate.string('Tell us exactly why you request the assistance')}
                   formatOnBlur
                   required />
        );

        return (
            <>
                <Field name="notificationForAssistance"
                       styleName="assistance-toggle"
                       component={ReduxCheckboxField}
                       componentLabel={Translate.string('Request startup assistance before the booking')}
                       disabled={disabled}
                       reactFinalForm={form}
                       toggle />
                <Field name="notificationForAssistance" reactFinalForm={form}>
                    {({input: {value}}) => value ? assistanceRequestReasonField : null}
                </Field>
            </>
        );
    }
}
