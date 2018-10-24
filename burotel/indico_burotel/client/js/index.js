import setup from 'indico/modules/rb_new/setup';

import parametrized from './parametrized';
import overrides from './overrides';
import reducers from './reducers';


setup({...parametrized, ...overrides}, reducers);
