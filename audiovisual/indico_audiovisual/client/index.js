// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {refreshCard} from './webcast_card';

import './style.scss';

const REFRESH_INTERVAL = 30000;

document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.av-webcast-card');
  if (!cards.length) {
    return;
  }
  cards.forEach(refreshCard);
  setInterval(() => cards.forEach(refreshCard), REFRESH_INTERVAL);
});
