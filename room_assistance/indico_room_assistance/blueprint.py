# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from indico.core.plugins import IndicoPluginBlueprint

from indico_room_assistance.controllers import RHRequestList


blueprint = IndicoPluginBlueprint('room_assistance', __name__, url_prefix='/service/room-assistance')
blueprint.add_url_rule('/', 'request_list', RHRequestList)
