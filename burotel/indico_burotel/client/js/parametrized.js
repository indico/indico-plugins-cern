import moment from 'moment';

// Import defaults that will be parametrized
import DefaultApp from 'indico/modules/rb_new/components/App';
import DefaultBookingBootstrapForm from 'indico/modules/rb_new/components/BookingBootstrapForm';
import DefaultMenu from 'indico/modules/rb_new/components/Menu';
import DefaultBookingFilterBar from 'indico/modules/rb_new/modules/bookRoom/BookingFilterBar';
import DefaultTimeInformation from 'indico/modules/rb_new/components/TimeInformation';
import DefaultBookRoom from 'indico/modules/rb_new/modules/bookRoom/BookRoom';
import DefaultRoomBookingMap from 'indico/modules/rb_new/common/map/RoomBookingMap';
import DefaultLandingStatistics from 'indico/modules/rb_new/modules/landing/LandingStatistics';
import {Translate} from 'indico/react/i18n';
import {parametrize} from 'indico/react/util';
import MapMarkers from './components/MapMarkers';


const App = parametrize(DefaultApp, {
    title: Translate.string('Burotel'),
    iconName: 'keyboard'
});

const BookingBootstrapForm = parametrize(DefaultBookingBootstrapForm, () => ({
    dayBased: true,
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
    dayBased: true
});

const BookRoom = parametrize(DefaultBookRoom, {
    showSuggestions: false
});

const TimeInformation = parametrize(DefaultTimeInformation, {
    timeSlot: null
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

export default {
    App,
    BookingBootstrapForm,
    BookingFilterBar,
    BookRoom,
    TimeInformation,
    LandingStatistics,
    Menu,
    RoomBookingMap
};
