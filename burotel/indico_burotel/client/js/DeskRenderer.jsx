import _ from 'underscore';
import React from 'react';
import PropTypes from 'prop-types';
import {Icon, Card} from 'semantic-ui-react';
import {Slot} from 'indico/react/util';

import '../styles/DeskRenderer.module.scss';


function Desk({desk: {name, division}, desk, actionRenderer}) {
    const {actions} = Slot.split(actionRenderer(desk));

    return (
        <Card>
            <Card.Content>
                <Card.Header>
                    {name}
                </Card.Header>
                <Card.Meta style={{fontSize: '0.8em'}}>
                    {division}
                </Card.Meta>
            </Card.Content>
            <Card.Content extra>
                {actions}
            </Card.Content>
        </Card>
    );
}

Desk.propTypes = {
    desk: PropTypes.object.isRequired,
    actionRenderer: PropTypes.func.isRequired
};

function RoomRenderer({id, desks, actionRenderer}) {
    return (
        <div styleName="room">
            <h3>{id}</h3>
            <Card.Group styleName="room-container">
                {desks.map(d => <Desk key={d.id} desk={d} actionRenderer={actionRenderer} />)}
            </Card.Group>
        </div>
    );
}

RoomRenderer.propTypes = {
    id: PropTypes.string.isRequired,
    desks: PropTypes.array.isRequired,
    actionRenderer: PropTypes.func.isRequired
};

function BuildingRenderer({id, rooms, actionRenderer}) {
    return (
        <div styleName="building">
            <h2><Icon name="building outline" /> {id}</h2>
            <div styleName="building-container">
                {rooms.map(([roomId, desks]) => {
                    return (
                        <RoomRenderer key={roomId}
                                      id={roomId}
                                      desks={desks}
                                      actionRenderer={actionRenderer} />
                    );
                })}
            </div>
        </div>
    );
}

BuildingRenderer.propTypes = {
    id: PropTypes.string.isRequired,
    rooms: PropTypes.array.isRequired,
    actionRenderer: PropTypes.func.isRequired
};

export default function DeskRenderer({rooms: desks, children}) {
    const byRoom = Object.entries(_.groupBy(desks, r => `${r.building}/${r.floor}-${r.number}`));
    const byBuilding = Object.entries(_.groupBy(byRoom, ([k]) => k.split('/')[0]));

    return byBuilding.map(([bldgId, rooms]) => (
        <BuildingRenderer key={bldgId} id={bldgId} rooms={rooms} actionRenderer={children} />
    ));
}
