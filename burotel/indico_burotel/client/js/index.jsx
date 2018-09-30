import moment from 'moment';
import React from 'react';
import setup from 'indico/modules/rb_new/setup';
import DefaultApp from 'indico/modules/rb_new/containers/App';
import DefaultBookingBootstrapForm from 'indico/modules/rb_new/components/BookingBootstrapForm';
import DefaultBookingFilterBar from 'indico/modules/rb_new/modules/bookRoom/BookingFilterBar';
import {TimeInformation as DefaultTimeInformation} from 'indico/modules/rb_new/modules/bookRoom/BookRoomModal';
import DefaultBookRoom from 'indico/modules/rb_new/modules/bookRoom/BookRoom';
import {Translate} from 'indico/react/i18n';
import BootstrapOptions from './BootstrapOptions';
import ExtraFilters from './ExtraFilters';

const parametrize = (Component, extraProps) => ({...props}) => {
    // handle deferred prop calculation
    if (typeof extraProps === 'function') {
        extraProps = extraProps();
    }

    // extraProps override props if there is a name collision
    const mergedProps = {...props, ...extraProps};
    const comp = <Component {...mergedProps} />;
    return comp;
}

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

setup({
    App,
    BookingBootstrapForm,
    BookingFilterBar,
    BookRoom,
    TimeInformation,
    'Landing.bootstrapOptions': BootstrapOptions,
    'RoomFilterBar.extraFilters': ExtraFilters
});
