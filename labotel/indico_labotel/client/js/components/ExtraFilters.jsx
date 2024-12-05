// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import divisionsURL from 'indico-url:plugin_labotel.divisions';

import PropTypes from 'prop-types';
import React from 'react';
import {Form} from 'semantic-ui-react';

import {FilterDropdownFactory} from 'indico/modules/rb/common/filters/FilterBar';
import FilterFormComponent from 'indico/modules/rb/common/filters/FilterFormComponent';
import {useIndicoAxios} from 'indico/react/hooks';
import {Translate} from 'indico/react/i18n';

// eslint-disable-next-line react/prop-types
const divisionRenderer = ({division}) => (!division ? null : <span>{division}</span>);

function DivisionFilter({division, setDivision}) {
  const {data: divisions} = useIndicoAxios(divisionsURL());

  return (
    <Form.Group>
      {divisions?.map(div => (
        <Form.Radio
          checked={division === div}
          key={div}
          label={div}
          onChange={() => {
            setDivision(div);
          }}
        />
      ))}
      <Form.Radio
        checked={!division}
        key="all"
        label={Translate.string('All')}
        onClick={() => setDivision(null)}
      />
    </Form.Group>
  );
}

DivisionFilter.propTypes = {
  division: PropTypes.string,
  setDivision: PropTypes.func.isRequired,
};

class ExtraFilterForm extends FilterFormComponent {
  state = {
    division: null,
  };

  setDivision(division) {
    const {setParentField} = this.props;

    setParentField('division', division);
    this.setState({
      division,
    });
  }

  render() {
    const {division} = this.state;
    return <DivisionFilter setDivision={this.setDivision.bind(this)} division={division} />;
  }
}

export default class ExtraFilters extends React.Component {
  static propTypes = {
    setFilter: PropTypes.func.isRequired,
    filters: PropTypes.object.isRequired,
    disabled: PropTypes.bool.isRequired,
  };

  render() {
    const {setFilter, filters, disabled} = this.props;
    return (
      <FilterDropdownFactory
        name="division"
        title={<Translate>Category</Translate>}
        form={({division}, setParentField) => (
          <ExtraFilterForm setParentField={setParentField} division={division} />
        )}
        setGlobalState={({division}) => setFilter('division', division)}
        initialValues={filters}
        renderValue={divisionRenderer}
        disabled={disabled}
      />
    );
  }
}
