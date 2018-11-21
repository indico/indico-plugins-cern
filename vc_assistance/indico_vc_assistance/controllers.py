# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask import session
from werkzeug.exceptions import Forbidden

from indico.web.rh import RHProtected
from indico_vc_assistance.util import is_vc_support


class RHRequestList(RHProtected):
    """Provides a list of webcast/recording requests"""

    def _check_access(self):
        RHProtected._check_access(self)
        if not is_vc_support(session.user):
            raise Forbidden

    def _process(self):
        return 'todo'
