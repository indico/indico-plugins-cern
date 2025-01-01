// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import Leaflet from 'leaflet';
import _ from 'lodash';
import PropTypes from 'prop-types';
import React from 'react';
import {Marker, Tooltip} from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-markercluster';
import {connect} from 'react-redux';

import {selectors as mapSelectors} from 'indico/modules/rb/common/map';
import {Translate, PluralTranslate, Singular, Plural, Param} from 'indico/react/i18n';

import styles from './MapMarkers.module.scss';

function groupIconCreateFunction(cluster) {
  const markers = cluster.getAllChildMarkers();
  const highlight = markers.some(m => m.options.highlight);
  const numSpaces = markers.reduce((acc, {options: {numSpaces: n}}) => acc + n, 0);

  return Leaflet.divIcon({
    html: numSpaces,
    className: `marker-cluster marker-cluster-small ${styles['map-cluster']} ${
      highlight ? 'highlight' : ''
    }`,
    iconSize: [40, 40],
  });
}

function generateMarker(hoveredRoomId, actions, {id, name, lat, lng, numSpaces}) {
  const icon = Leaflet.divIcon({
    html: `<span class="marker-building"><i class="building outline icon"></i>${name}</span>
               <span class="marker-number">&#xd7;${numSpaces}</span>`,
    className: styles['map-marker'],
    iconSize: ['auto', 'auto'],
  });
  const hoveredIcon = Leaflet.divIcon({
    className: `${styles['map-cluster']} highlight`,
    iconSize: [20, 20],
  });
  return (
    // we have to make the key depend on the highlighted state, otherwise
    // the component won't properly refresh (for some strange reason)
    <Marker
      key={id}
      position={[lat, lng]}
      numSpaces={numSpaces}
      building={name}
      icon={id === hoveredRoomId ? hoveredIcon : icon}
      highlight={id === hoveredRoomId}
      onClick={({
        target: {
          options: {building},
        },
      }) => {
        actions.setFilterParameter('building', building);
      }}
    >
      <Tooltip direction="top">
        <span>
          <Translate>
            Bldg. <Param name="name" value={name} />:
          </Translate>
        </span>{' '}
        <span>
          <PluralTranslate count={numSpaces}>
            <Singular>
              <Param name="count" value={numSpaces} /> lab
            </Singular>
            <Plural>
              <Param name="count" value={numSpaces} /> labs
            </Plural>
          </PluralTranslate>
        </span>
      </Tooltip>
    </Marker>
  );
}

function MapMarkers({rooms: spaces, hoveredRoomId, actions}) {
  const highlight = spaces.some(r => r.id === hoveredRoomId);
  const rooms = Object.values(_.groupBy(spaces, 'name')).map(spaceList => {
    const [{name, building, floor, number, lat, lng}] = spaceList;
    return {
      id: name,
      name,
      building,
      floor,
      number,
      lat,
      lng,
      spaces: spaceList.map(({id, fullName}) => ({id, name: fullName})),
    };
  });
  const buildings = Object.values(_.groupBy(rooms, 'building')).map(roomList => {
    const [{building, lat, lng}] = roomList;
    return {
      id: building,
      name: building,
      lat,
      lng,
      numSpaces: roomList.reduce((acc, {spaces: spaceList}) => acc + spaceList.length, 0),
      rooms: roomList.map(({id, name}) => ({id, name})),
    };
  });

  return (
    !!rooms.length && (
      <MarkerClusterGroup
        showCoverageOnHover
        iconCreateFunction={groupIconCreateFunction}
        // key is used here as a way to force a re-rendering
        // of the MarkerClusterGroup
        key={highlight}
      >
        {buildings
          .filter(({lat, lng}) => !!(lat && lng))
          .map(generateMarker.bind(undefined, hoveredRoomId, actions))}
      </MarkerClusterGroup>
    )
  );
}

MapMarkers.propTypes = {
  rooms: PropTypes.array,
  hoveredRoomId: PropTypes.number,
  actions: PropTypes.objectOf(PropTypes.func).isRequired,
};

MapMarkers.defaultProps = {
  rooms: [],
  hoveredRoomId: null,
};

export default connect(state => ({
  hoveredRoomId: mapSelectors.getHoveredRoom(state),
}))(MapMarkers);
