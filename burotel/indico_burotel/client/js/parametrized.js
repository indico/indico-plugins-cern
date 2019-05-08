// This file is part of the CERN Indico plugins.
// Copyright (C) 2014 - 2019 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import moment from 'moment';

// Import defaults that will be parametrized
import DefaultApp from 'indico/modules/rb/components/App';
import DefaultBookingBootstrapForm from 'indico/modules/rb/components/BookingBootstrapForm';
import DefaultMenu from 'indico/modules/rb/components/Menu';
import DefaultBookingFilterBar from 'indico/modules/rb/modules/bookRoom/BookingFilterBar';
import {RoomFilterBarBase} from 'indico/modules/rb/modules/roomList/RoomFilterBar';
import DefaultBookRoomModal from 'indico/modules/rb/modules/bookRoom/BookRoomModal';
import DefaultTimeInformation from 'indico/modules/rb/components/TimeInformation';
import DefaultBookRoom from 'indico/modules/rb/modules/bookRoom/BookRoom';
import DefaultRoomBookingMap from 'indico/modules/rb/common/map/RoomBookingMap';
import DefaultRoomDetailsModal from 'indico/modules/rb/common/rooms/RoomDetailsModal';
import DefaultLanding from 'indico/modules/rb/modules/landing/Landing';
import DefaultLandingStatistics from 'indico/modules/rb/modules/landing/LandingStatistics';
import DefaultCalendar from 'indico/modules/rb/modules/calendar/Calendar';
import DefaultTimelineItem from 'indico/modules/rb/common/timeline/TimelineItem';
import DefaultBookingEditForm from 'indico/modules/rb/common/bookings/BookingEditForm';
import DefaultSidebarMenu from 'indico/modules/rb/components/SidebarMenu';
import DefaultRoomList from 'indico/modules/rb/modules/roomList/RoomList';
import {UserSearch as DefaultUserSearch} from 'indico/react/components/principals/Search';
import {Translate} from 'indico/react/i18n';
import {parametrize} from 'indico/react/util';
import MapMarkers from './components/MapMarkers';


const App = parametrize(DefaultApp, {
    title: Translate.string('Burotel'),
    iconName: 'keyboard'
});

const BookingBootstrapForm = parametrize(DefaultBookingBootstrapForm, () => ({
    dayBased: true,
    hideOptions: {
        single: true,
        daily: false,
        recurring: true,
        timeSlot: true,
    },
    defaults: {
        recurrence: {
            type: 'daily'
        },
        dates: {
            endDate: moment().add(7, 'd')
        }
    }
}));

const BookingFilterBar = parametrize(DefaultBookingFilterBar, {
    dayBased: true,
});

const RoomFilterBar = parametrize(RoomFilterBarBase, {
    hideOptions: {
        capacity: true,
        favorites: true,
    }
});

const BookRoom = parametrize(DefaultBookRoom, {
    showSuggestions: false,
    labels: {
        bookButton: Translate.string('Book Desk'),
        preBookButton: Translate.string('Pre-Book Desk'),
        detailsButton: Translate.string('See details')
    }
});

const TimeInformation = parametrize(DefaultTimeInformation, {
    timeSlot: null
});

const Landing = parametrize(DefaultLanding, {
    showUpcomingBookings: false
});

const LandingStatistics = parametrize(DefaultLandingStatistics, () => ({
    labels: {
        activeRooms: Translate.string('Desks in use')
    }
}));

const RoomBookingMap = parametrize(DefaultRoomBookingMap, {
    markerComponent: MapMarkers
});

const Menu = parametrize(DefaultMenu, () => ({
    labels: {
        bookRoom: Translate.string('Book a Desk'),
        roomList: Translate.string('List of Spaces')
    }
}));

const RoomDetailsModal = parametrize(DefaultRoomDetailsModal, () => ({
    title: Translate.string('Desk Details')
}));

const BookRoomModal = parametrize(DefaultBookRoomModal, () => ({
    defaultTitles: {
        booking: Translate.string('Book a Desk'),
        preBooking: Translate.string('Pre-book a Desk')
    },
    reasonRequired: false,
}));

const Calendar = parametrize(DefaultCalendar, {
    allowDragDrop: false
});

const TimelineItem = parametrize(DefaultTimelineItem, {
    dayBased: true
});

const BookingEditForm = parametrize(DefaultBookingEditForm, {
    hideOptions: {
        single: true,
        daily: false,
        recurring: true,
        timeSlot: true,
    }
});

const SidebarMenu = parametrize(DefaultSidebarMenu, {
    hideOptions: {
        myBlockings: true,
    },
});

const RoomList = parametrize(DefaultRoomList, {
    hideActionsDropdown: true
});

const UserSearch = parametrize(DefaultUserSearch, {
    initialFormValues: {exact: true, external: true}
});

export default {
    App,
    BookingBootstrapForm,
    BookingFilterBar,
    BookRoom,
    BookRoomModal,
    Calendar,
    Landing,
    LandingStatistics,
    Menu,
    RoomBookingMap,
    RoomDetailsModal,
    RoomFilterBar,
    TimelineItem,
    TimeInformation,
    BookingEditForm,
    SidebarMenu,
    RoomList,
    UserSearch,
};
