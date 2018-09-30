# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_burotel.controllers import RHLanding


blueprint = _bp = IndicoPluginBlueprint('burotel', 'indico_burotel', url_prefix='/rooms-new')
# Frontend
_bp.add_url_rule('/', 'root', RHLanding)
_bp.add_url_rule('/book', 'landing', RHLanding)
