// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {push as pushRoute} from 'connected-react-router';
import React from 'react';
import {parametrize} from 'react-overridable';
import {Item} from 'semantic-ui-react';

// Import defaults that will be parametrized
import DefaultRoomBookingMap from 'indico/modules/rb/common/map/RoomBookingMap';
import DefaultRoomDetailsModal from 'indico/modules/rb/common/rooms/RoomDetailsModal';
import DefaultRoomRenderer from 'indico/modules/rb/common/rooms/RoomRenderer';
import DefaultApp from 'indico/modules/rb/components/App';
import DefaultMenu from 'indico/modules/rb/components/Menu';
import DefaultRoom from 'indico/modules/rb/components/Room';
import DefaultSidebarMenu from 'indico/modules/rb/components/SidebarMenu';
import DefaultBookFromListModal from 'indico/modules/rb/modules/bookRoom/BookFromListModal';
import DefaultBookRoom from 'indico/modules/rb/modules/bookRoom/BookRoom';
import DefaultBookRoomModal from 'indico/modules/rb/modules/bookRoom/BookRoomModal';
import DefaultLanding from 'indico/modules/rb/modules/landing/Landing';
import DefaultLandingStatistics from 'indico/modules/rb/modules/landing/LandingStatistics';
import {RoomFilterBarBase} from 'indico/modules/rb/modules/roomList/RoomFilterBar';
import DefaultRoomList from 'indico/modules/rb/modules/roomList/RoomList';
import {Translate} from 'indico/react/i18n';
import {ConditionalRoute} from 'indico/react/util';

import LabItem from './components/LabRenderer';
import MapMarkers from './components/MapMarkers';
import StatsPage from './components/StatsPage';

const App = parametrize(DefaultApp, {
  title: Translate.string('Labotel'),
  iconName: 'wrench',
  renderExtraRoutes(isInitializing) {
    // add statistics page
    return <ConditionalRoute path="/stats" component={StatsPage} active={!isInitializing} />;
  },
});

const RoomRenderer = parametrize(DefaultRoomRenderer, {
  containerComponent: ({children}) => (
    <div style={{marginTop: 30}}>
      <Item.Group divided>{children}</Item.Group>
    </div>
  ),
});

const Room = parametrize(DefaultRoom, {
  customRoomComponent: LabItem,
});

const RoomFilterBar = parametrize(RoomFilterBarBase, {
  hideOptions: {
    capacity: true,
  },
});

const BookRoom = parametrize(DefaultBookRoom, {
  showSuggestions: false,
  labels: {
    bookButton: null,
    preBookButton: null,
    detailsButton: Translate.string('See details'),
  },
});

const Landing = parametrize(DefaultLanding, {
  showUpcomingBookings: false,
});

const LandingStatistics = parametrize(DefaultLandingStatistics, () => ({
  labels: {
    activeRooms: Translate.string('Labs in use'),
  },
}));

const Menu = parametrize(DefaultMenu, () => ({
  labels: {
    bookRoom: Translate.string('Book a Resource'),
    roomList: Translate.string('List of Resources'),
  },
}));

const RoomBookingMap = parametrize(DefaultRoomBookingMap, {
  markerComponent: MapMarkers,
});

const RoomDetailsModal = parametrize(DefaultRoomDetailsModal, () => ({
  title: Translate.string('Resource Details'),
}));

const BookRoomModal = parametrize(DefaultBookRoomModal, () => ({
  defaultTitles: {
    booking: Translate.string('Book Resource'),
    preBooking: Translate.string('Pre-book Resource'),
  },
}));

const BookFromListModal = parametrize(DefaultBookFromListModal, () => ({
  labels: {
    bookTitle: Translate.string('Book Resource'),
    preBookTitle: Translate.string('Pre-book Resource'),
    bookBtn: Translate.string('Book'),
    preBookBtn: Translate.string('Pre-Book'),
  },
}));

const SidebarMenu = parametrize(DefaultSidebarMenu, ({dispatch}) => ({
  hideOptions: {
    myBlockings: true,
  },
  extraOptions: [
    {
      key: 'stats',
      icon: 'chart bar outline',
      text: Translate.string('Statistics'),
      onClick: () => {
        dispatch(pushRoute('/stats'));
      },
    },
  ],
}));

const RoomList = parametrize(DefaultRoomList, {
  hideActionsDropdown: true,
});

export default {
  App,
  BookRoom,
  BookRoomModal,
  BookFromListModal,
  Landing,
  LandingStatistics,
  Menu,
  RoomBookingMap,
  RoomDetailsModal,
  RoomFilterBar,
  SidebarMenu,
  RoomList,
  RoomRenderer,
  Room,
};
