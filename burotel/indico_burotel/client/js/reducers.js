import _ from 'lodash';
import {RESET_PAGE_STATE, INIT} from 'indico/modules/rb/actions';


export default [(state, action) => {
    if (action.type === INIT || action.type === RESET_PAGE_STATE) {
        const newState = _.cloneDeep(state);
        _.set(newState, 'bookRoom.timeline.datePicker.mode', 'weeks');
        _.set(newState, 'calendar.datePicker.mode', 'weeks');
        return newState;
    }
    return state;
}];
