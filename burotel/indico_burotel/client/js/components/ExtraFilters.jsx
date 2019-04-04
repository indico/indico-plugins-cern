/* This file is part of the CERN Indico plugins.
 * Copyright (C) 2014 - 2019 CERN
 *
 * The CERN Indico plugins are free software; you can redistribute
 * them and/or modify them under the terms of the MIT License; see
 * the LICENSE file for more details.
 */

import {Form} from 'semantic-ui-react';
import React from 'react';
import PropTypes from 'prop-types';
import {Translate} from 'indico/react/i18n';
import {FilterDropdownFactory} from 'indico/modules/rb_new/common/filters/FilterBar';
import FilterFormComponent from 'indico/modules/rb_new/common/filters/FilterFormComponent';
import {EXPERIMENTS} from './BootstrapOptions';

// eslint-disable-next-line react/prop-types
const divisionRenderer = ({division}) => (
    (!division) ? null : (
        <span>
            {division}
        </span>
    ));


class ExtraFilterForm extends FilterFormComponent {
    state = {
        division: null
    };

    setDivision(division) {
        const {setParentField} = this.props;

        setParentField('division', division);
        this.setState({
            division
        });
    }

    render() {
        const {division} = this.state;
        return (
            <>
                <Form.Group>
                    {EXPERIMENTS.map(div => (
                        <Form.Radio checked={division === div}
                                    key={div}
                                    label={div}
                                    onChange={() => {
                                        this.setDivision(div);
                                    }} />
                    ))}
                    <Form.Radio checked={!division}
                                key="all"
                                label={Translate.string('All')}
                                onClick={() => this.setDivision(null)} />
                </Form.Group>
            </>
        );
    }
}

export default class ExtraFilters extends React.Component {
    static propTypes = {
        setFilter: PropTypes.func.isRequired,
        filters: PropTypes.object.isRequired
    };

    render() {
        const {setFilter, filters} = this.props;
        return (
            <FilterDropdownFactory name="division"
                                   title={<Translate>Experiment</Translate>}
                                   form={({division}, setParentField) => (
                                       <ExtraFilterForm setParentField={setParentField}
                                                        division={division} />
                                   )}
                                   setGlobalState={({division}) => setFilter('division', division)}
                                   initialValues={filters}
                                   renderValue={divisionRenderer} />
        );
    }
}
