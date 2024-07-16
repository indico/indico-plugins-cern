// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import getLabotelStatsCSV from 'indico-url:plugin_labotel.stats_csv';

import _ from 'lodash';
import moment from 'moment';
import React, {useState} from 'react';
import {Button, Dropdown, Form} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import Stats from './Stats';
import './StatsPage.module.scss';

const CURRENT_YEAR = moment().year();
const CURRENT_MONTH = moment().month();
const YEARS = _.times(10, i => {
  const year = CURRENT_YEAR - i;
  return {
    key: year,
    text: year,
    value: year,
  };
});
const NUMBER_MONTHS = _.times(12, i => ({
  key: i,
  text: i + 1,
  value: i + 1,
}));
const DEFAULT_MONTHS = 12;

export default function StatsPage() {
  const [year, setYear] = useState(CURRENT_YEAR);
  const [month, setMonth] = useState(CURRENT_MONTH);
  const [numMonths, setNumMonths] = useState(DEFAULT_MONTHS);

  const months = _.times(12, m => {
    return {
      key: m,
      value: m,
      text: moment()
        .month(m)
        .format('MMMM'),
      disabled: year === CURRENT_YEAR && m > moment().month(),
    };
  });

  const endDate = moment()
    .month(month)
    .endOf('month')
    .year(year);
  const startDate = endDate
    .clone()
    .subtract(numMonths - 1, 'months')
    .startOf('month');

  return (
    <div styleName="stats-page">
      <h2>
        <Translate>Labotel Statistics</Translate>
      </h2>
      <Form>
        <Form.Group inline>
          <Form.Field>
            <label>
              <Translate>Number of months</Translate>
            </label>
            <Dropdown
              compact
              selection
              options={NUMBER_MONTHS}
              value={numMonths}
              onChange={(__, {value}) => setNumMonths(value)}
            />
          </Form.Field>
          <Form.Field>
            <label>
              <Translate>Until</Translate>
            </label>
            <Dropdown
              selection
              options={months}
              value={month}
              onChange={(__, {value}) => setMonth(value)}
            />
          </Form.Field>
          <Form.Field>
            <Dropdown
              selection
              compact
              options={YEARS}
              onChange={(__, {value}) => {
                setYear(value);
                if (value === CURRENT_YEAR && month > CURRENT_MONTH) {
                  setMonth(CURRENT_MONTH);
                }
              }}
              value={year}
            />
          </Form.Field>
          <Button
            styleName="stats-csv-button"
            as="a"
            content="CSV"
            icon="download"
            href={getLabotelStatsCSV({
              start_month: startDate.format('YYYY-MM'),
              end_month: endDate.format('YYYY-MM'),
            })}
          />
        </Form.Group>
      </Form>
      <Stats startDate={startDate} endDate={endDate} />
    </div>
  );
}
