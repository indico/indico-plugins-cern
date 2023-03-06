# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.cache import make_scoped_cache
from indico.util.i18n import make_bound_gettext


_ = make_bound_gettext('conversion')
pdf_state_cache = make_scoped_cache('pdf-conversion')
cloudconvert_task_cache = make_scoped_cache('pdf-conversion-cloudconvert-tasks')
