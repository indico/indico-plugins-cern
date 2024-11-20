// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';
import PropTypes from 'prop-types';
import {Item} from 'semantic-ui-react';

import {Slot, Markdown} from 'indico/react/util';

import SpriteImage from 'indico/modules/rb/components/SpriteImage';

import './LabRenderer.module.scss';

function LabItem({lab, actionRenderer, ...rest}) {
    const {actions} = Slot.split(actionRenderer(lab));
    return (
        <Item {...rest} key={lab.id} styleName="lab-item">
            <Item.Image size="small" styleName="lab-item-image">
                <SpriteImage pos={lab.spritePosition} width="100%" height="100%" />
            </Item.Image>
            <Item.Content>
                <Item.Header styleName="lab-item-header">
                    {lab.fullName}
                    <div>
                        {actions}
                    </div>
                </Item.Header>
                <Item.Meta>{lab.division}</Item.Meta>
                <Item.Description>
                    <Markdown disallowedElements={['br']}>{lab.comments}</Markdown>
                </Item.Description>
            </Item.Content>
        </Item>
    );
};

export default function LabRenderer({rooms: labs, children}) {
    return (
        <div style={{marginTop: 30}}>
            <Item.Group divided>
            {labs.map(lab => (
                <LabItem key={lab.id} lab={lab} actionRenderer={children} />
            ))}
            </Item.Group>
        </div>
    );
}

LabRenderer.propTypes = {
    rooms: PropTypes.array.isRequired,
    children: PropTypes.func.isRequired,
};
