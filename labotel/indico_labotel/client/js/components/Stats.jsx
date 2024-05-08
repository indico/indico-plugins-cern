// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import getLabotelStats from 'indico-url:plugin_labotel.stats';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import {Chart} from 'react-charts';
import {Table, Loader} from 'semantic-ui-react';

import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';

import './StatsPage.module.scss';

function interpolateRGB(color1, color2, ratio) {
  return _.zip(color1, color2).map(([c1, c2]) => Math.round(c1 * ratio + c2 * (1 - ratio)));
}

function toHex(color) {
  return `#${_.map(color, c => c.toString(16).padStart(2, '0')).join('')}`;
}

const PALETTE = [[204, 0, 0], [0, 200, 81]];

const AXES = [
  {primary: true, type: 'ordinal', position: 'bottom'},
  {type: 'linear', position: 'left'},
];

function calculateChartData(data, monthInfo) {
  const rows = data.reduce((accum, [building, data]) => {
    data.forEach(([experiment, expData]) => {
      accum.push([building, experiment, expData]);
    });
    return accum;
  }, []);
  const experimentsByMonth = _.mapValues(_.groupBy(rows, ([, experiment]) => experiment), rows_ =>
    _.zip(...rows_.map(([, , {months}]) => months)).map(a => _.sum(a))
  );
  return Object.entries(experimentsByMonth).map(([k, months]) => ({
    label: k,
    data: months.map((m, i) => [monthInfo[i].name, m]),
  }));
}

const toPercent = number => (Math.round(number * 10000) / 100).toFixed(2);

function PercentCell({value, total, highlight}) {
  const ratio = value / total;
  const color = interpolateRGB(PALETTE[1], PALETTE[0], ratio);
  return (
    <Table.Cell
      style={{color: toHex(color)}}
      styleName={highlight ? 'cell-highlight' : 'cell-normal'}
    >
      {`${toPercent(ratio)}%`}
      <div className="percentage">{value}</div>
    </Table.Cell>
  );
}

PercentCell.propTypes = {
  value: PropTypes.number.isRequired,
  total: PropTypes.number.isRequired,
  highlight: PropTypes.bool,
};

PercentCell.defaultProps = {
  highlight: false,
};

function StatsTable({data, numDays, months}) {
  return (
    <div>
      <div styleName="stats-chart-wrapper">
        <div styleName="stats-chart">
          <Chart data={calculateChartData(data, months)} axes={AXES} tooltip dark />
        </div>
      </div>
      <Table striped>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>
              <Translate>Building</Translate>
            </Table.HeaderCell>
            <Table.HeaderCell>
              <Translate>Category</Translate>
            </Table.HeaderCell>
            <Table.HeaderCell>
              <Translate>Number of desks</Translate>
            </Table.HeaderCell>
            {months.map(({name}) => (
              <Table.HeaderCell key={name}>{name}</Table.HeaderCell>
            ))}
            <Table.HeaderCell>
              <Translate>Total</Translate>
            </Table.HeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {data.map(([building, experiments]) =>
            experiments.map(([experiment, {bookings, deskCount, months: monthData}]) => (
              <Table.Row key={`row-${building}-${experiment}`}>
                <Table.Cell>{building}</Table.Cell>
                <Table.Cell>{experiment}</Table.Cell>
                <Table.Cell>{deskCount}</Table.Cell>
                {monthData.map((value, i) => (
                  <PercentCell
                    key={`month-${months[i].id}`}
                    value={value}
                    total={deskCount * months[i].numDays}
                  />
                ))}
                <PercentCell value={bookings} total={deskCount * numDays} highlight />
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table>
    </div>
  );
}

StatsTable.propTypes = {
  numDays: PropTypes.number.isRequired,
  data: PropTypes.arrayOf(PropTypes.array).isRequired,
  months: PropTypes.arrayOf(PropTypes.object).isRequired,
};

export default function Stats({startDate, endDate}) {
  const {loading, data} = useIndicoAxios(
    getLabotelStats({
      start_month: startDate.format('YYYY-MM'),
      end_month: endDate.format('YYYY-MM'),
    }),
    {camelize: true}
  );

  return loading || !data ? <Loader active /> : <StatsTable {...data} />;
}

Stats.propTypes = {
  startDate: PropTypes.object.isRequired,
  endDate: PropTypes.object.isRequired,
};
