// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import PropTypes from 'prop-types';
import React from 'react';
import {useDispatch} from 'react-redux';
import {Item} from 'semantic-ui-react';

import {actions as roomActions} from 'indico/modules/rb/common/rooms';
import SpriteImage from 'indico/modules/rb/components/SpriteImage';
import {Slot, Markdown} from 'indico/react/util';

import './LabRenderer.module.scss';

export default function LabItem({roomInstance, room}) {
  const {actions} = Slot.split(roomInstance.props.children);
  const dispatch = useDispatch();
  const openRoomDetails = () => dispatch(roomActions.openRoomDetailsBook(room.id));
  return (
    <Item key={room.id} styleName="lab-item">
      <Item.Image
        size="small"
        styleName="lab-item-image"
        onClick={() => openRoomDetails(room.id)}
        style={{cursor: 'pointer'}}
      >
        <SpriteImage pos={room.spritePosition} width="100%" height="100%" />
      </Item.Image>
      <Item.Content>
        <Item.Header styleName="lab-item-header">
          <div>
            <span onClick={() => openRoomDetails(room.id)} style={{cursor: 'pointer'}}>
              {room.fullName}
            </span>{' '}
            {roomInstance.renderRoomStatus()}
          </div>
          <div>
            {actions}
            {roomInstance.renderFavoriteButton()}
          </div>
        </Item.Header>
        <Item.Meta>{room.division}</Item.Meta>
        <Item.Description>
          <Markdown targetBlank>{room.comments}</Markdown>
        </Item.Description>
      </Item.Content>
    </Item>
  );
}

LabItem.propTypes = {
  roomInstance: PropTypes.object.isRequired,
  room: PropTypes.object.isRequired,
};
