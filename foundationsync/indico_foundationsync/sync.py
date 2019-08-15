# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import re
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager

from html2text import HTML2Text
from sqlalchemy.orm.exc import NoResultFound

from indico.core.db.sqlalchemy import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.groups import GroupProxy
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.rooms import Room
from indico.modules.users.util import get_user_by_email


try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None


DEFAULT_VC_EQUIPMENT = {'Vidyo'}


class SkipRoom(Exception):
    pass


def OutputTypeHandler(cursor, name, defaultType, size, precision, scale):
    """
    Unicode output handler for oracle connections
    Source: http://www.oracle.com/technetwork/articles/dsl/tuininga-cx-oracle-084866.html
    """
    if defaultType in (cx_Oracle.STRING, cx_Oracle.FIXED_CHAR):
        return cursor.var(unicode, size, cursor.arraysize)


class FoundationSync(object):
    def __init__(self, db_name, logger):
        self.db_name = db_name
        self._logger = logger

        if cx_Oracle is None:
            raise RuntimeError('cx_Oracle is not installed')

        try:
            self._location = Location.query.filter_by(name='CERN', is_deleted=False).one()
        except NoResultFound:
            self._logger.exception("Synchronization failed: Location CERN not found in Indico DB")
            raise

    @contextmanager
    def connect_to_foundation(self):
        try:
            connection = cx_Oracle.connect(self.db_name)
            connection.outputtypehandler = OutputTypeHandler
            self._logger.debug("Connected to Foundation DB")
            yield connection
            connection.close()
        except cx_Oracle.DatabaseError:
            self._logger.exception("Problem connecting to DB")
            raise

    def _html_to_markdown(self, s):
        s = re.sub(r'<font color=[^> ]+>(.+?)</font>', r'<strong>\1</strong>', s)
        return HTML2Text(bodywidth=0).handle(s).strip()

    def _parse_room_data(self, raw_data, coordinates, room_id):
        data = {}
        data['building'] = raw_data['BUILDING']
        data['floor'] = raw_data['FLOOR']
        data['number'] = raw_data['ROOM_NUMBER']
        email = raw_data['RESPONSIBLE_EMAIL']
        if not data['building'] or not data['floor'] or not data['number']:
            raise SkipRoom('Error in Foundation - No value for BUILDING or FLOOR or ROOM_NUMBER')

        email_warning = None
        if not email:
            email_warning = ('[%s] No value for RESPONSIBLE_EMAIL in Foundation', room_id)
            user = None
        else:
            user = get_user_by_email(email, create_pending=True)
            if not user:
                email_warning = ('[%s] Bad RESPONSIBLE_EMAIL in Foundation: no user found with email %s',
                                 email, room_id)

        data['owner'] = user
        data['verbose_name'] = (raw_data.get('FRIENDLY_NAME') or '').strip() or None
        data['capacity'] = int(raw_data['CAPACITY']) if raw_data['CAPACITY'] else None
        data['surface_area'] = int(raw_data['SURFACE']) if raw_data['SURFACE'] else None
        data['division'] = raw_data.get('DEPARTMENT')
        data['telephone'] = raw_data.get('TELEPHONE') or ''
        data['key_location'] = self._html_to_markdown(raw_data.get('WHERE_IS_KEY') or '')
        data['comments'] = self._html_to_markdown(raw_data.get('COMMENTS')) if raw_data.get('COMMENTS') else ''
        data['reservations_need_confirmation'] = raw_data['BOOKINGS_NEED_CONFIRMATION'] != 'N'

        is_reservable = raw_data['IS_RESERVABLE'] != 'N'
        data['protection_mode'] = ProtectionMode.public if is_reservable else ProtectionMode.protected
        site = raw_data.get('SITE')
        site_map = {'MEYR': 'Meyrin', 'PREV': 'Prevessin'}
        data['site'] = site_map.get(site, site)

        building_coordinates = coordinates.get(int(data['building']))
        if building_coordinates:
            data['latitude'] = building_coordinates['latitude']
            data['longitude'] = building_coordinates['longitude']

        return data, email_warning

    def _prepare_row(self, row, cursor):
        return dict(zip([d[0] for d in cursor.description], row))

    def _update_room(self, room, room_data):
        room.is_deleted = False
        room.is_reservable = True
        for k, v in room_data.iteritems():
            if getattr(room, k) != v:
                setattr(room, k, v)
        db.session.flush()

    def fetch_buildings_coordinates(self, connection):
        self._logger.debug("Fetching the building geocoordinates...")

        coordinates = {}
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM aispub.loc_cl_cur_ouvrage')

        for row in cursor:
            row = self._prepare_row(row, cursor)
            longitude = row['LONGITUDE']
            latitude = row['LATITUDE']
            building_number = int(row['NO_OUVRAGE']) if row['NO_OUVRAGE'] else None

            if latitude and longitude and building_number:
                coordinates[building_number] = {'latitude': latitude, 'longitude': longitude}

        self._logger.debug("Fetched geocoordinates for %d buildings", len(coordinates))
        return coordinates

    def fetch_equipment(self, connection):
        self._logger.debug("Fetching equipment list...")

        counter = Counter()
        foundation_equipment_ids = []
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM foundation_pub.equipment ORDER BY NAME')

        for row in cursor:
            row = self._prepare_row(row, cursor)
            counter['found'] += 1
            equipment = EquipmentType.find_first(EquipmentType.name == row['NAME'])
            if not equipment:
                equipment = EquipmentType(name=row['NAME'])
                db.session.add(equipment)
                counter['added'] += 1
                self._logger.info(u"Added equipment '%s'", equipment)
            foundation_equipment_ids.append(equipment.id)

        for equipment in EquipmentType.find(~EquipmentType.id.in_(foundation_equipment_ids)):
            self._logger.info("Mismatch: Equipment '%s' found in Indico but not in Foundation", equipment.name)

        db.session.commit()
        self._logger.info("Equipment objects summary: %d found - %d new added", counter['found'], counter['added'])

    def fetch_rooms(self, connection, room_name=None):
        self._logger.debug("Fetching room information...")

        counter = Counter()
        foundation_rooms = []

        coordinates = self.fetch_buildings_coordinates(connection)
        cursor = connection.cursor()

        if room_name:
            cursor.execute('SELECT * FROM foundation_pub.meeting_rooms WHERE ID = :room_name', room_name=room_name)
        else:
            cursor.execute('SELECT * FROM foundation_pub.meeting_rooms ORDER BY ID')

        for row in cursor:
            counter['found'] += 1
            data = self._prepare_row(row, cursor)
            room_id = data['ID']

            try:
                room_data, email_warning = self._parse_room_data(data, coordinates, room_id)
                manager_group = data.get('EMAIL_LIST')
                self._logger.debug("Fetched data for room with id='%s'", room_id)
            except SkipRoom as e:
                counter['skipped'] += 1
                self._logger.info("Skipped room %s: %s", room_id, e)
                continue

            room = Room.query.filter_by(building=room_data['building'], floor=room_data['floor'],
                                        number=room_data['number'], location=self._location).first()

            if room_data['owner'] is None:
                del room_data['owner']
                if room is None:
                    counter['skipped'] += 1
                    self._logger.info("Skipped room %s: %s", room_id, email_warning[0] % email_warning[1:])
                    continue
                elif not room.is_deleted:
                    self._logger.warning(*email_warning)

            # Insert new room
            if room is None:
                room = Room()
                self._location.rooms.append(room)
                counter['inserted'] += 1
                self._logger.info("Created new room '%s'", room_id)
            else:
                counter['updated'] += 1

            # Update room data
            self._update_room(room, room_data)
            new_managers = set()
            if manager_group is not None:
                group = GroupProxy(manager_group.strip(), provider='cern-ldap')
                if group.group is None:
                    self._logger.warning("Group '%s' does not exist in LDAP", manager_group)
                new_managers.add(group)
            current_managers = room.get_manager_list()
            for principal in current_managers - new_managers:
                room.update_principal(principal, full_access=False)
            for principal in new_managers - current_managers:
                room.update_principal(principal, full_access=True)

            self._logger.info("Updated room '%s' information", room_id)
            foundation_rooms.append(room)

        # Deactivate rooms not found in Foundation
        indico_rooms = Room.find(Room.name == room_name) if room_name else Room.find(location=self._location)
        rooms_to_deactivate = (room for room in indico_rooms if room not in foundation_rooms and not room.is_deleted)
        for room in rooms_to_deactivate:
            self._logger.info("Deactivated room '%s'", room.full_name)
            room.is_deleted = True
            counter['deactivated'] += 1
        self._logger.info("Deactivated %d rooms not found in Foundation", counter['deactivated'])

        db.session.commit()
        self._logger.info("Rooms summary: %d in Foundation - %d skipped - %d inserted - %d updated - %d deactivated",
                          counter['found'], counter['skipped'], counter['inserted'], counter['updated'],
                          counter['deactivated'])

    def fetch_room_equipment(self, connection, room_name=None):
        self._logger.debug("Fetching rooms equipment...")

        cursor = connection.cursor()
        if room_name:
            cursor.execute('SELECT * FROM foundation_pub.room_equipment WHERE MEETING_ROOM_ID = :room_name',
                           room_name=room_name)
        else:
            cursor.execute('SELECT * FROM foundation_pub.room_equipment ORDER BY MEETING_ROOM_ID')

        counter = Counter()
        foundation_room_equipment = defaultdict(list)
        for row in cursor:
            row = self._prepare_row(row, cursor)
            counter['found'] += 1

            room_id = row['MEETING_ROOM_ID'].strip().replace(' ', '-')
            equipment_name = row['EQUIPMENT_NAME']
            if equipment_name == 'Video conference':
                equipment_name = 'Vidyo'
            building, floor, number = room_id.split('-')

            equipment = EquipmentType.query.filter_by(name=equipment_name).first()
            room = Room.query.filter_by(building=building, floor=floor, number=number).first()
            try:
                if not room:
                    raise SkipRoom('Room not found in Indico DB')
                if not equipment:
                    raise SkipRoom('Equipment %s not found in Indico DB', equipment_name)
                if equipment not in room.available_equipment:
                    room.available_equipment.append(equipment)
                    counter['added'] += 1
                    self._logger.info("Added equipment '%s' to room '%s'", equipment.name, room.full_name)
                foundation_room_equipment[room].append(equipment.id)
            except SkipRoom as e:
                counter['skipped'] += 1
                self._logger.info("Skipped room %s: %s", room_id, e)

        for room, equipment_types in foundation_room_equipment.iteritems():
            foundation_equipment_ids = set(equipment_types)
            for equipment in room.available_equipment:
                if equipment.id in foundation_equipment_ids:
                    continue
                room.available_equipment.remove(equipment)
                counter['deleted'] += 1
                self._logger.info("Deleted equipment '%s' from room '%s'", equipment.name, room.full_name)

        db.session.commit()
        self._logger.info("Equipment associations summary: %d found - %d new added - %d skipped - %d deleted",
                          counter['found'], counter['added'], counter['skipped'], counter['deleted'])

    def run_all(self, room_name=None):
        with self.connect_to_foundation() as connection:
            try:
                self.fetch_rooms(connection, room_name)
                self.fetch_equipment(connection)
                self.fetch_room_equipment(connection, room_name)
            except Exception:
                self._logger.exception("Synchronization with Foundation failed")
                raise
