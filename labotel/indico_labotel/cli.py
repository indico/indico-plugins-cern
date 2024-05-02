# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import csv

import click
import requests
from flask_pluginengine import current_plugin
from pyproj import Proj, transform

from indico.cli.core import cli_group
from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.groups import GroupProxy
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.modules.users.util import get_user_by_email
from indico.util.console import cformat


GIS_URL = 'https://maps.cern.ch/arcgis/rest/services/Batiments/GeocodeServer/findAddressCandidates?postal={}&f=json'
ROOM_FIELDS = ('id', 'division', 'building', 'floor', 'number', 'verbose_name', 'owner', 'acl_entries')
group_cache = {}
latlon_cache = {}
user_cache = {}


@cli_group(name='labotel')
def cli():
    """Manage the Labotel plugin."""


def check_changed_fields(original, new):
    diff = []
    for field in ROOM_FIELDS:
        if field == 'acl_entries':
            orig_value = {e.principal for e in original.acl_entries}
            target_value = new['acl_entries']
        else:
            orig_value = getattr(original, field)
            target_value = new[field]
        if orig_value != target_value:
            diff.append((field, orig_value, target_value))
    return diff


def get_location(building):
    location = Location.query.filter(Location.name == f'Area {building}', ~Location.is_deleted).first()
    if not location:
        location = Location(name=f'Area {building}')
        print(cformat('%{green!}+%{reset} Adding new location for building {}').format(building))
        db.session.add(location)
        db.session.flush()
    return location


def get_user(email):
    if email not in user_cache:
        user_cache[email] = get_user_by_email(email)
    return user_cache[email]


def get_principal(name):
    if '@' in name:
        return get_user(name)

    # otherwise we assume it's a group's name
    cern_ident_provider = current_plugin.settings.get('cern_identity_provider')
    group = group_cache.setdefault(name, GroupProxy(name, provider=cern_ident_provider))
    if not group or not group.group:
        group = None
        print(cformat("%{red}!%{reset} Group %{cyan}{}%{reset} doesn't seem to exist!").format(name))
    return group


def get_room(room_id):
    room = Room.get(room_id)
    if not room:
        print(cformat('%{yellow}! Desk with ID {} not found.').format(room_id))
    return room


def change_room(room, changes):
    for field, __, new_value in changes:
        if field == 'acl_entries':
            # clear the ACL and add the new principals
            room.acl_entries.clear()
            db.session.flush()
            for p in new_value:
                room.update_principal(p, full_access=True)
        else:
            setattr(room, field, new_value)


def _print_changes(room, changes):
    print(f'[{room}]:')
    for field, old, new in changes:
        if field == 'acl_entries':
            old = {e.name for e in old}
            new = {e.name for e in new}
        print(cformat(' %{yellow}>%{reset} %{cyan}{}%{reset}: %{red}{}%{reset} -> %{green}{}%{reset}')
              .format(field, old, new))
    print()


def _principal_repr(p):
    return getattr(p.principal, 'email', p.principal.name)


def get_latlon_building(building_num):
    if building_num not in latlon_cache:
        # this API request should get the positions of a building's
        # entrance doors
        data = requests.get(GIS_URL.format(building_num)).json()

        # local EPSG reference used in results
        epsg_ref = Proj(init='epsg:{}'.format(data['spatialReference']['wkid']))

        counter = 0
        x, y = 0, 0

        for c in data['candidates']:
            x += c['location']['x']
            y += c['location']['y']
            counter += 1

        # average position of entrance doors
        x /= counter
        y /= counter

        # these coordinates are relative to a local EPSG reference.
        # we'll have to convert them to EPSG:4326, used by GPS
        latlon_ref = Proj(init='epsg:4326')
        lon, lat = transform(epsg_ref, latlon_ref, x, y)

        latlon_cache[building_num] = (lat, lon)
        print(cformat('%{cyan}{}%{reset}: %{green}{}%{reset}, %{green}{}%{reset}').format(building_num, lat, lon))
    return latlon_cache[building_num]


@cli.command()
@click.argument('csv_file', type=click.File('r'))
@click.option('--add-missing', is_flag=True, help='Add UPDATE rooms that do not exist locally')
@click.option('--dry-run', is_flag=True, help="Don't actually change the database, just report on the changes")
def update(csv_file, add_missing, dry_run):
    """Update the Labotels from a CSV file."""
    num_changes = 0
    num_adds = 0
    num_removes = 0
    r = csv.reader(csv_file)

    valid_ids = {id_ for id_, in db.session.query(Room.id)}
    for room_id, division, building, floor, number, verbose_name, owner_email, acl_row, action in r:
        owner = get_user(owner_email)
        acl = {get_principal(principal) for principal in acl_row.split(';')} if acl_row else None

        data = {
            'id': int(room_id.decode('utf-8-sig')) if room_id else None,
            'division': division,
            'building': building,
            'floor': floor,
            'number': number,
            'verbose_name': verbose_name,
            'owner': owner,
            'acl_entries': ({owner} | acl) if acl else {owner},
            'action': action or 'UPDATE'
        }
        if not data['id'] and action != 'ADD':
            print(cformat('%{yellow}! Only ADD lines can have an empty Desk ID. Ignoring line.'))
            continue

        if add_missing and data['action'] == 'UPDATE' and data['id'] not in valid_ids:
            data['action'] = 'ADD'
            print(cformat('%{yellow}! Desk with ID {} not found; adding it.').format(room_id))

        if data['action'] == 'UPDATE':
            room = get_room(room_id)
            if not room:
                continue
            changes = check_changed_fields(room, data)
            if changes:
                num_changes += 1
                _print_changes(room, changes)
                if not dry_run:
                    change_room(room, changes)
        elif data['action'] == 'ADD':
            existing_room = Room.query.filter(Room.building == building,
                                              Room.floor == floor,
                                              Room.number == number,
                                              Room.verbose_name == verbose_name).first()
            if existing_room:
                # a room with the exact same designation already exists
                print(cformat('%{yellow}!%{reset} A lab with the name %{cyan}{}%{reset} already exists')
                      .format(existing_room.full_name))
                continue
            print(cformat('%{green!}+%{reset} New lab %{cyan}{}/{}-{} {}').format(
                building, floor, number, verbose_name))
            num_adds += 1
            if not dry_run:
                room = Room(building=building, floor=floor, number=number, division=division,
                            verbose_name=verbose_name, owner=owner, location=get_location(building),
                            protection_mode=ProtectionMode.protected, reservations_need_confirmation=True)
                room.update_principal(owner, full_access=True)
                if acl:
                    for principal in acl:
                        room.update_principal(principal, full_access=True)
                db.session.add(room)
        elif data['action'] == 'REMOVE':
            room = get_room(room_id)
            if not room:
                continue
            print(cformat('%{red}-%{reset} {}').format(room.full_name))
            if not dry_run:
                room.is_deleted = True
            num_removes += 1

    print(cformat('\n%{cyan}Total:%{reset} %{green}+%{reset}{}  %{yellow}\u00b1%{reset}{}  %{red}-%{reset}{} ')
          .format(num_adds, num_changes, num_removes))

    if not dry_run:
        db.session.commit()


@cli.command()
@click.argument('csv_file', type=click.File('w'))
def export(csv_file):
    """Export lab list to a CSV file."""
    writer = csv.writer(csv_file)
    for desk in Room.query.filter(~Room.is_deleted).order_by(Room.building, Room.floor, Room.number, Room.verbose_name):
        groups = ';'.join(_principal_repr(p) for p in desk.acl_entries)
        writer.writerow((desk.id, desk.division, desk.building, desk.floor, desk.number, desk.verbose_name,
                         desk.owner.email, groups, ''))


@cli.command()
@click.option('--dry-run', is_flag=True, help="Don't actually change the database, just report on the changes")
def geocode(dry_run):
    """Set geographical location for all labs/buildings."""
    for desk in Room.query.filter(~Room.is_deleted):
        latlon = get_latlon_building(desk.building)
        if not dry_run:
            desk.latitude, desk.longitude = latlon
    if not dry_run:
        db.session.commit()
