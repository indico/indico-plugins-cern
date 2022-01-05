# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import redirect
from werkzeug.exceptions import NotFound

from indico.core.plugins import IndicoPluginBlueprint
from indico.modules.rb.models.rooms import Room


blueprint = IndicoPluginBlueprint('foundationsync', __name__)


@blueprint.route('!/rooms/resolve/<building>/<floor>-<number>')
def resolve_room(building, floor, number):
    room = Room.query.filter(
        ~Room.is_deleted,
        Room.building == building,
        Room.floor == floor,
        Room.number == number
    ).one_or_none()
    if not room:
        raise NotFound
    return redirect(room.details_url)
