// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {push as pushRoute} from 'connected-react-router';
import React from 'react';
import {parametrize} from 'react-overridable';

// Import defaults that will be parametrized
import DefaultRoomDetailsModal from 'indico/modules/rb/common/rooms/RoomDetailsModal';
import DefaultApp from 'indico/modules/rb/components/App';
import DefaultMenu from 'indico/modules/rb/components/Menu';
import DefaultSidebarMenu from 'indico/modules/rb/components/SidebarMenu';
import DefaultBookRoom from 'indico/modules/rb/modules/bookRoom/BookRoom';
import DefaultBookRoomModal from 'indico/modules/rb/modules/bookRoom/BookRoomModal';
import DefaultLanding from 'indico/modules/rb/modules/landing/Landing';
import DefaultLandingStatistics from 'indico/modules/rb/modules/landing/LandingStatistics';
import {RoomFilterBarBase} from 'indico/modules/rb/modules/roomList/RoomFilterBar';
import DefaultRoomList from 'indico/modules/rb/modules/roomList/RoomList';
import {Translate} from 'indico/react/i18n';
import {ConditionalRoute} from 'indico/react/util';

import StatsPage from './components/StatsPage';

const App = parametrize(DefaultApp, {
  title: Translate.string('Labotel'),
  iconName: 'wrench',
  renderExtraRoutes(isInitializing) {
    // add statistics page
    return <ConditionalRoute path="/stats" component={StatsPage} active={!isInitializing} />;
  },
});

const RoomFilterBar = parametrize(RoomFilterBarBase, {
  hideOptions: {
    capacity: true,
  },
});

const BookRoom = parametrize(DefaultBookRoom, {
  showSuggestions: false,
  labels: {
    bookButton: Translate.string('Book Lab'),
    preBookButton: Translate.string('Pre-Book Lab'),
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
    bookRoom: Translate.string('Book a Lab'),
    roomList: Translate.string('List of Spaces'),
  },
}));

const RoomDetailsModal = parametrize(DefaultRoomDetailsModal, () => ({
  title: Translate.string('Lab Details'),
}));

const BookRoomModal = parametrize(DefaultBookRoomModal, () => ({
  defaultTitles: {
    booking: Translate.string('Book a Lab'),
    preBooking: Translate.string('Pre-book a Lab'),
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
  Landing,
  LandingStatistics,
  Menu,
  RoomDetailsModal,
  RoomFilterBar,
  SidebarMenu,
  RoomList,
};
