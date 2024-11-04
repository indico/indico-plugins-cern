// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import defaultDivisionURL from 'indico-url:plugin_labotel.user_division';

import React, {useEffect, useRef} from 'react';

import {Landing} from 'indico/modules/rb/modules/landing/Landing';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

export default function LabotelLanding(props) {
  const landing = useRef();

  useEffect(() => {
    (async () => {
      let response;
      try {
        response = await indicoAxios.get(defaultDivisionURL());
      } catch (error) {
        handleAxiosError(error);
        return;
      }
      const division = response.data.value;
      if (landing.current && division) {
        landing.current.setExtraState({division});
      }
    })();
  }, []);

  return <Landing ref={landing} {...props} />;
}
