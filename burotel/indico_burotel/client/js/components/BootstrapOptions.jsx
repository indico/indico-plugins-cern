/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2019 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import {Button} from 'semantic-ui-react';
import React from 'react';
import PropTypes from 'prop-types';
import {Translate} from 'indico/react/i18n';


export const EXPERIMENTS = ['ATLAS', 'CMS', 'ALICE'];

export default class BootstrapOptions extends React.Component {
    static propTypes = {
        setOptions: PropTypes.func.isRequired,
        options: PropTypes.object.isRequired
    };

    render() {
        const {setOptions, options: {division}} = this.props;

        return (
            <Button.Group style={{marginBottom: 10}}>
                {EXPERIMENTS.map(experiment => (
                    <Button key={experiment}
                            onClick={() => setOptions({division: experiment})}
                            primary={division === experiment}>
                        {experiment}
                    </Button>
                ))}
                <Button key="other"
                        onClick={() => setOptions({division: null})}
                        primary={!division}>
                    <Translate>All</Translate>
                </Button>
            </Button.Group>
        );
    }
}
