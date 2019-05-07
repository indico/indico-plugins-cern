import setup from 'indico/modules/rb/setup';

import parametrized from './parametrized';
import overrides from './overrides';
import reducers from './reducers';


setup({...parametrized, ...overrides}, reducers);
