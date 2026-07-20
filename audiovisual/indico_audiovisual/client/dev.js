// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {applyState} from './webcast_card';

document.addEventListener('DOMContentLoaded', () => {
  const devRoot = document.querySelector('#av-webcast-dev');
  if (!devRoot) {
    return;
  }
  const now = Date.now();
  const mockStates = {
    fallback: {state: 'unavailable', streamStartDateTime: null, streamStopDateTime: null},
    upcoming: {state: 'upcoming', streamStartDateTime: null, streamStopDateTime: null},
    live: {
      state: 'live',
      streamStartDateTime: new Date(now - 23 * 60000).toISOString(),
      streamStopDateTime: null,
    },
    ended: {
      state: 'ended',
      streamStartDateTime: new Date(now - 81 * 60000).toISOString(),
      streamStopDateTime: new Date(now - 23 * 60000).toISOString(),
    },
  };
  devRoot.querySelectorAll('[data-specimen-state]').forEach(spec => {
    const card = spec.querySelector('.av-webcast-card');
    applyState(card, mockStates[spec.dataset.specimenState]);
  });
  devRoot.querySelectorAll('[data-mock-state]').forEach(btn => {
    btn.addEventListener('click', () => {
      const webcastState = mockStates[btn.dataset.mockState];
      devRoot.querySelectorAll('.js-interactive .av-webcast-card').forEach(card => applyState(card, webcastState));
    });
  });
});
