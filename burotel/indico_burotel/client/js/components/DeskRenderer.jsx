import _ from 'underscore';
import React from 'react';
import PropTypes from 'prop-types';
import {Icon, Card} from 'semantic-ui-react';
import {withHoverListener} from 'indico/modules/rb_new/common/map/util';
import {Slot} from 'indico/react/util';

import './DeskRenderer.module.scss';


function Desk({desk: {name, division}, desk, actionRenderer, ...rest}) {
    const {actions} = Slot.split(actionRenderer(desk));

    return (
        <Card {...rest}>
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
    const DeskComponent = withHoverListener(({room: desk, ...rest}) => (
        <Desk key={desk.id} desk={desk} actionRenderer={actionRenderer} {...rest} />
    ));

    return (
        <div styleName="room">
            <h3>{id}</h3>
            <Card.Group styleName="room-container">
                {desks.map(d => <DeskComponent key={d.id} room={d} />)}
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
                {rooms.map(([roomId, desks]) => (
                    <RoomRenderer key={roomId}
                                  id={roomId}
                                  desks={desks}
                                  actionRenderer={actionRenderer} />
                ))}
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
    children: PropTypes.func.isRequired
};
