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
import {connect} from 'react-redux';
import {bindActionCreators} from 'redux';

import SpriteImage from 'indico/modules/rb/components/SpriteImage';
import {actions as roomActions} from 'indico/modules/rb/common/rooms';

import './LabRenderer.module.scss';

function LabItem({roomInstance, openRoomDetails}) {
    const {room} = roomInstance.props;
    const {actions} = Slot.split(roomInstance.props.children);
    return (
        <Item key={room.id} styleName="lab-item">
            <Item.Image size="small" styleName="lab-item-image" onClick={() => openRoomDetails(room.id)} style={{cursor: 'pointer'}}>
                <SpriteImage pos={room.spritePosition} width="100%" height="100%" />
            </Item.Image>
            <Item.Content>
                <Item.Header styleName="lab-item-header">
                    <div onClick={() => openRoomDetails(room.id)} style={{cursor: 'pointer'}}>{room.fullName}</div>
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

LabItem.propTypes = {
    roomInstance: PropTypes.object.isRequired,
    openRoomDetails: PropTypes.func.isRequired,
};

export function LabRenderer({roomInstance, openRoomDetails}) {
   return <LabItem roomInstance={roomInstance} openRoomDetails={openRoomDetails} />;
}

LabRenderer.propTypes = {
    roomInstance: PropTypes.object.isRequired,
    openRoomDetails: PropTypes.func.isRequired,
};

const mapDispatchToProps = dispatch => ({
    openRoomDetails: bindActionCreators(roomActions.openRoomDetailsBook, dispatch),
});

export default connect(null, mapDispatchToProps)(LabRenderer);
