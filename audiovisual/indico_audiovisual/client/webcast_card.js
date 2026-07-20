// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

/* global moment */

import {bindTranslateComponents} from 'indico/react/i18n';

const {Translate} = bindTranslateComponents('audiovisual');

const SUPPORTED_STATES = ['upcoming', 'live', 'ended'];
const RELATIVE_TIME_THRESHOLDS = {m: 60, h: 24};

function formatStreamDuration(ms) {
  const minutes = Math.max(1, Math.round(ms / 60000));
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (Intl.DurationFormat) {
    return new Intl.DurationFormat(moment.locale(), {style: 'narrow'}).format({hours, minutes: mins});
  }
  // TODO: drop the fallback once the browserslist floor clears chrome 129 / firefox 136
  if (!hours) {
    return Translate.string('{mins}m', {mins});
  }
  return mins
    ? Translate.string('{hours}h {mins}m', {hours, mins})
    : Translate.string('{hours}h', {hours});
}

function setSublineText(sub, text) {
  sub.classList.toggle('hidden', !text);
  sub.querySelector('.js-sub-text').textContent = text;
}

function updateCountdown(card) {
  const countdown = card.querySelector('.js-countdown');
  const startDt = Date.parse(card.dataset.plannedStartDt || '');
  if (countdown && !Number.isNaN(startDt)) {
    const diff = startDt - Date.now();
    countdown.textContent =
      diff > 60000
        ? moment.duration(diff).humanize(false, RELATIVE_TIME_THRESHOLDS)
        : Translate.string('a moment');
  }
}

function updateLiveSubline(card) {
  const sub = card.querySelector('.js-live-sub');
  const started = Date.parse(card.dataset.streamStartDt || '');
  const text = Number.isNaN(started)
    ? ''
    : Translate.string('Started {ago}', {
        ago: moment.duration(started - Date.now()).humanize(true, RELATIVE_TIME_THRESHOLDS),
      });
  setSublineText(sub, text);
}

function updateEndedSubline(card) {
  const sub = card.querySelector('.js-ended-sub');
  const started = Date.parse(card.dataset.streamStartDt || '');
  const stopped = Date.parse(card.dataset.streamStopDt || '');
  let text = '';
  if (!Number.isNaN(started)) {
    const tz = card.dataset.tz;
    const startMoment = tz ? moment(started).tz(tz) : moment(started);
    text = Translate.string('Streamed {date}', {date: startMoment.format('ddd ll')});
    if (!Number.isNaN(stopped) && stopped > started) {
      text += ` · ${formatStreamDuration(stopped - started)}`;
    }
  }
  setSublineText(sub, text);
}

export function refreshCard(card) {
  const state = card.dataset.state;
  if (state === 'upcoming') {
    updateCountdown(card);
  } else if (state === 'live') {
    updateLiveSubline(card);
  } else if (state === 'ended') {
    updateEndedSubline(card);
  }
}

export function applyState(card, webcastState) {
  card.dataset.state = SUPPORTED_STATES.includes(webcastState.state)
    ? webcastState.state
    : 'fallback';
  if (webcastState.streamStartDateTime) {
    card.dataset.streamStartDt = webcastState.streamStartDateTime;
  } else {
    delete card.dataset.streamStartDt;
  }
  if (webcastState.streamStopDateTime) {
    card.dataset.streamStopDt = webcastState.streamStopDateTime;
  } else {
    delete card.dataset.streamStopDt;
  }
  refreshCard(card);
}
