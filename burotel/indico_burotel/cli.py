# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import click
import csv

from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.cli.core import cli_group
from indico.modules.groups import GroupProxy
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.modules.users.util import get_user_by_email
from indico.util.console import cformat


ROOM_FIELDS = ('id', 'division', 'building', 'floor', 'number', 'verbose_name', 'owner', 'acl_entries')
group_cache = {}


@cli_group(name='burotel')
def cli():
    """Manage the Burotel plugin."""


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
    location = Location.query.filter(Location.name == "Area {}".format(building)).first()
    if not location:
        location = Location(name="Area {}".format(building))
        print(cformat("%{green!}+%{reset} Adding new location for building {}").format(building))
        db.session.add(location)
        db.session.flush()
    return location


def get_group(name):
    group = group_cache.setdefault(name, GroupProxy(name, provider='cern-ldap'))
    if not group or not group.group:
        group = None
        print cformat("%{red}!%{reset} Group %{cyan}{}%{reset} doesn't seem to exist!").format(name)
    return group


def change_room(room, changes):
    for field, _, new_value in changes:
        if field == 'acl_entries':
            # clear the ACL and add the new principals
            room.acl_entries.clear()
            db.session.flush()
            for p in new_value:
                room.update_principal(p, full_access=True)
        else:
            setattr(room, field, new_value)


def _print_changes(room, changes):
    print '[{}]:'.format(room)
    for field, old, new in changes:
        if field == 'acl_entries':
            old = {e.name for e in old}
            new = {e.name for e in new}
        print (cformat(' %{yellow}>%{reset} %{cyan}{}%{reset}: %{red}{}%{reset} -> %{green}{}%{reset}')
               .format(field, old, new))
    print


@cli.command()
@click.argument('csv_file', type=click.File('rb'))
@click.option('--dry-run', is_flag=True, help="Don't actually change the database, just report on the changes")
def update(csv_file, dry_run):
    """Update the Burotels from a CSV file."""
    num_changes = 0
    num_adds = 0
    num_removes = 0
    r = csv.reader(csv_file)

    for room_id, division, building, floor, number, verbose_name, owner_email, egroup, action in r:
        owner = get_user_by_email(owner_email)
        group = get_group(egroup) if egroup else None

        data = {
            'id': int(room_id.decode('utf-8-sig')) if room_id else None,
            'division': division,
            'building': building,
            'floor': floor,
            'number': number,
            'verbose_name': verbose_name,
            'owner': owner,
            'acl_entries': {owner, group} if group else {owner},
            'action': action or 'UPDATE'
        }
        if not data['id'] and action != 'ADD':
            print cformat("%{yellow}! Only ADD lines can have an empty Desk ID. Ignoring line.")
            continue
        elif data['action'] == 'UPDATE':
            room = Room.get(room_id)
            if not room:
                print cformat("%{yellow}! Desk with ID {} not found.").format(room_id)
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
                print (cformat("%{yellow}!%{reset} A desk with the name %{cyan}{}%{reset} already exists")
                       .format(existing_room.name))
                continue
            print cformat("%{green!}+%{reset} New desk %{cyan}{}/{}-{} {}").format(
                building, floor, number, verbose_name)
            num_adds += 1
            if not dry_run:
                room = Room(building=building, floor=floor, number=number, division=division,
                            verbose_name=verbose_name, owner=owner, location=get_location(building),
                            protection_mode=ProtectionMode.protected)
                db.session.add(room)
        elif data['action'] == 'REMOVE':
            room = Room.get(room_id)
            print cformat("%{red}-%{reset} {}").format(room.name)
            if not dry_run:
                room.is_active = False
            num_removes += 1

    print (cformat("\n%{cyan}Total:%{reset} %{green}+%{reset}{}  %{yellow}\u00b1%{reset}{}  %{red}-%{reset}{} ")
           .format(num_adds, num_changes, num_removes))

    if not dry_run:
        db.session.commit()
