// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import defaultDivisionURL from 'indico-url:plugin_labotel.user_division';

import React from 'react';

import {Landing} from 'indico/modules/rb/modules/landing/Landing';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

export default class LabotelLanding extends React.Component {
  constructor(props) {
    super(props);
    this.landing = React.createRef();
  }

  async componentDidMount() {
    let response;
    try {
      response = await indicoAxios.get(defaultDivisionURL());
    } catch (error) {
      handleAxiosError(error);
      return;
    }
    const division = response.data.value;
    if (this.landing.current && division) {
      this.landing.current.setExtraState({division});
    }
  }

  render() {
    return <Landing ref={this.landing} {...this.props} />;
  }
}
