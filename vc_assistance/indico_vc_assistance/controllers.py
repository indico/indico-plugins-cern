# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.web.rh import RHProtected


class RHRequestList(RHProtected):
    """Provides a list of webcast/recording requests"""

    # def _check_access(self):
    #     RHProtected._check_access(self)
    #     if not is_av_manager(session.user):
    #         raise Forbidden

    def _process(self):
        return 'test.'
