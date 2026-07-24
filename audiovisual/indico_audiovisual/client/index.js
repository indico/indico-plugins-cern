// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {applyState, initCard, refreshCard} from './webcast_card';

import './style.scss';

const REFRESH_INTERVAL = 30000;

function subscribeToStateUpdates(card) {
  const base = card.dataset.stateUrl;
  if (!base) {
    return;
  }
  const url = new URL(base);
  const token = card.dataset.viewerToken;
  if (token) {
    url.searchParams.set('token', token);
  }
  const source = new EventSource(url);
  source.addEventListener('state', evt => {
    let webcastState;
    try {
      webcastState = JSON.parse(evt.data);
    } catch {
      return;
    }
    applyState(card, webcastState);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.av-webcast-card');
  if (!cards.length) {
    return;
  }
  cards.forEach(initCard);
  cards.forEach(subscribeToStateUpdates);
  setInterval(() => cards.forEach(refreshCard), REFRESH_INTERVAL);
});
