// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import React from 'react';
import {Item} from 'semantic-ui-react';
import {Slot, Markdown} from 'indico/react/util';

import SpriteImage from 'indico/modules/rb/components/SpriteImage';

import './LabRenderer.module.scss';

function LabItem({roomInstance}) {
    const {room} = roomInstance.props;
    const {actions} = Slot.split(roomInstance.props.children);
    return (
        <Item key={room.id} styleName="lab-item">
            <Item.Image size="small" styleName="lab-item-image">
                <SpriteImage pos={room.spritePosition} width="100%" height="100%" />
            </Item.Image>
            <Item.Content>
                <Item.Header styleName="lab-item-header">
                    {room.fullName}
                    <div>
                        {actions}
                        {roomInstance.renderFavoriteButton()}
                    </div>
                </Item.Header>
                <Item.Meta>{room.division}</Item.Meta>
                <Item.Description>
                    <Markdown disallowedElements={['br']}>{room.comments}</Markdown>
                </Item.Description>
            </Item.Content>
        </Item>
    );
}

export default function LabRenderer({roomInstance}) {
   return <LabItem roomInstance={roomInstance} />;
}
