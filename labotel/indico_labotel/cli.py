# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import click
import requests
from pyproj import Transformer

from indico.cli.core import cli_group
from indico.core.db import db
from indico.modules.rb.models.rooms import Room
from indico.util.console import cformat


GIS_URL = 'https://maps.cern.ch/arcgis/rest/services/Batiments/GeocodeServer/findAddressCandidates?postal={}&f=json'
latlon_cache = {}


@cli_group(name='labotel')
def cli():
    """Manage the Labotel plugin."""


def get_latlon_building(building_num):
    try:
        return latlon_cache[building_num]
    except KeyError:
        # this API request should get the positions of a building's entrance doors
        data = requests.get(GIS_URL.format(building_num)).json()

        # average position of entrance doors
        x = sum(c['location']['x'] for c in data['candidates']) / len(data['candidates'])
        y = sum(c['location']['y'] for c in data['candidates']) / len(data['candidates'])

        # transform to correct GPS coordinate system
        transformer = Transformer.from_crs(f'epsg:{data['spatialReference']['wkid']}', 'epsg:4326')
        lat, lon = transformer.transform(x, y)

        latlon_cache[building_num] = lat, lon
        print(cformat('%{cyan}{}%{reset}: %{green}{}%{reset}, %{green}{}%{reset}').format(building_num, lat, lon))
        return latlon_cache[building_num]


@cli.command()
@click.option('--dry-run', is_flag=True, help="Don't actually change the database, just report on the changes")
def geocode(dry_run):
    """Set geographical location for all labs/buildings."""
    for lab in Room.query.filter(~Room.is_deleted):
        latlon = get_latlon_building(lab.building)
        if not dry_run:
            lab.latitude, lab.longitude = latlon
    if not dry_run:
        db.session.commit()
