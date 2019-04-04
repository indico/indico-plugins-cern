/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2019 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import defaultExperimentURL from 'indico-url:plugin_burotel.user_experiment';

import {Button} from 'semantic-ui-react';
import React from 'react';
import PropTypes from 'prop-types';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';
import {Translate} from 'indico/react/i18n';


export const EXPERIMENTS = ['ATLAS', 'CMS', 'ALICE', 'LHCb'];

export default class BootstrapOptions extends React.Component {
    static propTypes = {
        setOptions: PropTypes.func.isRequired,
        options: PropTypes.object.isRequired
    };

    handleExperimentClick = async (experiment) => {
        const {setOptions} = this.props;
        setOptions({division: experiment});
        try {
            await indicoAxios.post(defaultExperimentURL(), {value: experiment});
        } catch (error) {
            handleAxiosError(error);
        }
    };

    render() {
        const {options: {division}} = this.props;

        return (
            <Button.Group style={{marginBottom: 10}}>
                {EXPERIMENTS.map(experiment => (
                    <Button key={experiment}
                            onClick={() => this.handleExperimentClick(experiment)}
                            primary={division === experiment}>
                        {experiment}
                    </Button>
                ))}
                <Button key="other"
                        onClick={() => this.handleExperimentClick(null)}
                        primary={!division}>
                    <Translate>All</Translate>
                </Button>
            </Button.Group>
        );
    }
}
