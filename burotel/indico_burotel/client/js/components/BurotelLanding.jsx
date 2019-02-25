/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2019 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import defaultExperimentURL from 'indico-url:plugin_burotel.user_experiment';

import React from 'react';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';
import {Landing} from 'indico/modules/rb_new/modules/landing/Landing';


export default class BurotelLanding extends React.Component {
    constructor(props) {
        super(props);
        this.landing = React.createRef();
    }

    async componentDidMount() {
        let response;
        try {
            response = await indicoAxios.get(defaultExperimentURL());
        } catch (error) {
            handleAxiosError(error);
            return;
        }
        const experiment = response.data.value;
        if (this.landing.current && experiment) {
            this.landing.current.setExtraState({division: 'ATLAS'});
        }
    }

    render() {
        return <Landing ref={this.landing} {...this.props} />;
    }
}
