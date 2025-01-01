// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import {Icon, Card} from 'semantic-ui-react';

import {withHoverListener} from 'indico/modules/rb/common/map/util';
import {Translate} from 'indico/react/i18n';
import {Slot} from 'indico/react/util';

import './DeskRenderer.module.scss';

function Desk({desk: {fullName, division, isLongTerm}, desk, actionRenderer, ...rest}) {
  const {actions} = Slot.split(actionRenderer(desk));

  return (
    <Card {...rest} styleName={isLongTerm && 'long-term-desk'}>
      <Card.Content>
        <Card.Header>{fullName}</Card.Header>
        <Card.Meta style={{fontSize: '0.8em'}}>{division}</Card.Meta>
      </Card.Content>
      <Card.Content extra styleName="extra-content">
        {actions}
        {isLongTerm && (
          <span styleName="long-term-label">
            <Translate>Long term</Translate>
          </span>
        )}
      </Card.Content>
    </Card>
  );
}

Desk.propTypes = {
  desk: PropTypes.object.isRequired,
  actionRenderer: PropTypes.func.isRequired,
};

function RoomRenderer({id, desks, actionRenderer}) {
  const DeskComponent = withHoverListener(({room: desk, ...rest}) => (
    <Desk key={desk.id} desk={desk} actionRenderer={actionRenderer} {...rest} />
  ));

  return (
    <div styleName="room">
      <h3>{id}</h3>
      <Card.Group styleName="room-container">
        {desks.map(d => (
          <DeskComponent key={d.id} room={d} />
        ))}
      </Card.Group>
    </div>
  );
}

RoomRenderer.propTypes = {
  id: PropTypes.string.isRequired,
  desks: PropTypes.array.isRequired,
  actionRenderer: PropTypes.func.isRequired,
};

function BuildingRenderer({id, rooms, actionRenderer}) {
  return (
    <div styleName="building">
      <h2>
        <Icon name="building outline" /> {id}
      </h2>
      <div styleName="building-container">
        {rooms.map(([roomId, desks]) => (
          <RoomRenderer key={roomId} id={roomId} desks={desks} actionRenderer={actionRenderer} />
        ))}
      </div>
    </div>
  );
}

BuildingRenderer.propTypes = {
  id: PropTypes.string.isRequired,
  rooms: PropTypes.array.isRequired,
  actionRenderer: PropTypes.func.isRequired,
};

export default function DeskRenderer({rooms: desks, children}) {
  const byRoom = Object.entries(_.groupBy(desks, r => `${r.building}/${r.floor}-${r.number}`));
  const byBuilding = Object.entries(_.groupBy(byRoom, ([k]) => k.split('/')[0]));

  return (
    <div style={{marginTop: 30}}>
      {byBuilding.map(([bldgId, rooms]) => (
        <BuildingRenderer key={bldgId} id={bldgId} rooms={rooms} actionRenderer={children} />
      ))}
    </div>
  );
}

DeskRenderer.propTypes = {
  rooms: PropTypes.array.isRequired,
  children: PropTypes.func.isRequired,
};
