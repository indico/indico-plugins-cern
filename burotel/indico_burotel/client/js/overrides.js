import DeskRenderer from './components/DeskRenderer';
import BootstrapOptions from './components/BootstrapOptions';
import ExtraFilters from './components/ExtraFilters';
import DailyButton from './components/DailyButton';
import BurotelLanding from './components/BurotelLanding';
import RowLabel from './components/RowLabel';

export default {
    'Landing': BurotelLanding,
    'RoomRenderer': DeskRenderer,
    'Landing.bootstrapOptions': BootstrapOptions,
    'RoomFilterBar.extraFilters': ExtraFilters,
    'BookingFilterBar.recurrence': DailyButton,
    'TimelineContent.rowLabel': RowLabel,
};
