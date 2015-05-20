"""
Synchronizes holidays, rooms and equipment with the CERN Foundation Database.
"""

import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from logging import StreamHandler

from celery.schedules import crontab
from flask_pluginengine import with_plugin_context
from sqlalchemy.orm.exc import NoResultFound
from wtforms import StringField

from indico.core.celery import celery
from indico.core.plugins import IndicoPlugin
from indico.core.db import DBMgr
from indico.core.db.sqlalchemy import db
from indico.core.db.sqlalchemy.util.session import update_session_options
from indico.modules.rb.models.holidays import Holiday
from indico.modules.rb.models.locations import Location
from indico.modules.rb.models.equipment import EquipmentType
from indico.modules.rb.models.rooms import Room
from indico.modules.users.util import get_user_by_email
from indico.web.forms.base import IndicoForm

try:
    import cx_Oracle
except ImportError:
    cx_Oracle = None


DEFAULT_VC_EQUIPMENT = {'Built-in (MCU) Bridge', 'Vidyo', 'H323 point2point', 'Audio Conference'}


def OutputTypeHandler(cursor, name, defaultType, size, precision, scale):
    """
    Unicode output handler for oracle connections
    Source: http://www.oracle.com/technetwork/articles/dsl/tuininga-cx-oracle-084866.html
    """
    if defaultType in (cx_Oracle.STRING, cx_Oracle.FIXED_CHAR):
        return cursor.var(unicode, size, cursor.arraysize)


class FoundationSync(object):
    def __init__(self, db_name, logger):
        update_session_options(db)
        self.db_name = db_name
        self._logger = logger
        try:
            self._location = Location.find(Location.name == 'CERN').one()
        except NoResultFound:
            self._logger.exception("Synchronization failed: Location CERN not found in Indico DB")
            raise

    @contextmanager
    def connect_to_foundation(self):
        try:
            connection = cx_Oracle.connect(self.db_name)
            connection.outputtypehandler = OutputTypeHandler
            self._logger.info("Connected to Foundation DB")
            yield connection
            connection.close()
        except cx_Oracle.DatabaseError:
            self._logger.exception("Problem connecting to DB")
            raise

    def _get_room_attrs(self, raw_data):
        return {'manager-group': raw_data.get('EMAIL_LIST'),
                'allowed-booking-group': raw_data.get('BOOKING_EMAIL_LIST')}

    def _parse_room_data(self, raw_data, coordinates):
        data = {}

        data['building'] = raw_data['BUILDING']
        data['floor'] = raw_data['FLOOR']
        data['number'] = raw_data['ROOM_NUMBER']
        data['email'] = raw_data['RESPONSIBLE_EMAIL']
        if not data['building'] or not data['floor'] or not data['number']:
            raise ValueError('Error in Foundation - No value for BUILDING or FLOOR or ROOM_NUMBER')
        if not data['email']:
            raise ValueError('Error in Foundation - No value for RESPONSIBLE_EMAIL')

        user = get_user_by_email(data['email'], create_pending=True)
        if not user:
            raise ValueError('Bad RESPONSIBLE_EMAIL in Foundation - No user found with email {}'.format(data['email']))

        data['owner'] = user
        data['name'] = (raw_data.get('FRIENDLY_NAME') or '').strip()
        data['capacity'] = int(raw_data['CAPACITY']) if raw_data['CAPACITY'] else None
        data['surface_area'] = int(raw_data['SURFACE']) if raw_data['SURFACE'] else None
        data['division'] = raw_data.get('DEPARTMENT')
        data['telephone'] = raw_data.get('TELEPHONE')
        data['key_location'] = raw_data.get('WHERE_IS_KEY')
        data['comments'] = raw_data.get('COMMENTS')
        data['is_reservable'] = raw_data['IS_RESERVABLE'] != 'N'
        data['reservations_need_confirmation'] = raw_data['BOOKINGS_NEED_CONFIRMATION'] != 'N'

        site = raw_data.get('SITE')
        site_map = {'MEYR': 'Meyrin', 'PREV': 'Prevessin'}
        data['site'] = site_map.get(site, site)

        building_coordinates = coordinates.get(int(data['building']))
        if building_coordinates:
            data['latitude'] = building_coordinates['latitude']
            data['longitude'] = building_coordinates['longitude']

        return data

    def _prepare_row(self, row, cursor):
        return dict(zip([d[0] for d in cursor.description], row))

    def _update_room(self, room, room_data, room_attrs):
        room.is_active = True
        for k, v in room_data.iteritems():
            setattr(room, k, v)
        for attribute, value in room_attrs.iteritems():
            room.set_attribute_value(attribute, value)
        room.update_name()
        return room

    def fetch_buildings_coordinates(self, connection):
        self._logger.info("Fetching the building geocoordinates...")

        coordinates = {}
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM geosip_pub.ouvrage')

        for row in cursor:
            row = self._prepare_row(row, cursor)
            longitude = row['LONGITUDE']
            latitude = row['LATITUDE']
            building_number = int(row['NUMERO']) if row['NUMERO'] else None

            if latitude and longitude and building_number:
                coordinates[building_number] = {'latitude': latitude, 'longitude': longitude}

        self._logger.info("Fetched geocoordinates for {} buildings".format(len(coordinates)))
        return coordinates

    def fetch_equipment(self, connection):
        self._logger.info("Fetching equipment list...")

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
                self._location.equipment_types.append(equipment)
                counter['added'] += 1
                self._logger.info(u"Added equipment '{}'".format(equipment))
            foundation_equipment_ids.append(equipment.id)

        vc_parent = self._location.get_equipment_by_name('Video conference')
        for equipment in EquipmentType.find(~EquipmentType.id.in_(foundation_equipment_ids),
                                            EquipmentType.parent_id != vc_parent.id):
            self._logger.info("Mismatch: Equipment '{}' found in Indico but not in Foundation".format(equipment.name))

        db.session.commit()
        self._logger.info("Equipment objects summary: {} found - {} new added".format(counter['found'],
                                                                                      counter['added']))

    def fetch_holidays(self, connection):
        self._logger.info("Fetching holidays...")

        counter = Counter()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM FOUNDATION_PUB.OFFICIAL_HOLIDAYS "
                       "WHERE COMMENTS NOT IN ('Saturday', 'Sunday') "
                       "ORDER BY HOLIDAY_DATE ASC")

        self._location.holidays.delete()
        for row in cursor:
            row = self._prepare_row(row, cursor)
            holiday = Holiday(date=row['HOLIDAY_DATE'].date(), name=row['COMMENTS'])
            counter['found'] += 1
            self._location.holidays.append(holiday)
            self._logger.info(u"Added {} as a holiday ({})".format(holiday.date, holiday.name))

        db.session.commit()
        self._logger.info("Holidays summary: {} found".format(counter['found']))

    def fetch_rooms(self, connection, room_name=None):
        self._logger.info("Fetching room information...")

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
                room_data = self._parse_room_data(data, coordinates)
                room_attrs = self._get_room_attrs(data)
                self._logger.info("Fetched data for room with id='{}'".format(room_id))
            except ValueError as e:
                counter['skipped'] += 1
                self._logger.warning("Skipped room {}: {}".format(room_id, str(e)))
                continue

            room = Room.find_first(Room.building == room_data['building'],
                                   Room.floor == room_data['floor'],
                                   Room.number == room_data['number'])

            # Insert new room
            if room is None:
                room = Room()
                self._location.rooms.append(room)
                counter['inserted'] += 1
                self._logger.info("Created new room '{}'".format(room_id))
            else:
                counter['updated'] += 1

            # Update room data
            room = self._update_room(room, room_data, room_attrs)
            self._logger.info("Updated room '{}' information".format(room_id))

            foundation_rooms.append(room)

        # Deactivate rooms not found in Foundation
        indico_rooms = Room.find(Room.name == room_name) if room_name else Room.find()
        rooms_to_deactivate = (room for room in indico_rooms if room not in foundation_rooms and room.is_active)
        for room in rooms_to_deactivate:
            room.is_active = False
            room.is_reservable = False
            counter['deactivated'] += 1
        self._logger.info("Deactivated {} rooms not found in Foundation".format(counter['deactivated']))

        db.session.commit()
        self._logger.info("Rooms summary: {} in Foundation - {} skipped - {} inserted - {} updated - {} deactivated"
                          .format(counter['found'], counter['skipped'], counter['inserted'], counter['updated'],
                                  counter['deactivated']))

    def fetch_room_equipment(self, connection, room_name=None):
        self._logger.info("Fetching rooms equipment...")

        cursor = connection.cursor()
        if room_name:
            cursor.execute('SELECT * FROM foundation_pub.room_equipment WHERE MEETING_ROOM_ID = :room_name',
                           room_name=room_name)
        else:
            cursor.execute('SELECT * FROM foundation_pub.room_equipment ORDER BY MEETING_ROOM_ID')

        counter = Counter()
        foundation_room_equipment = defaultdict(list)
        vc_parent = self._location.get_equipment_by_name('Video conference')
        vc_equipment = set(self._location.equipment_types
                           .filter(EquipmentType.parent_id == vc_parent.id,
                                   EquipmentType.name.in_(DEFAULT_VC_EQUIPMENT))
                           .all())

        for row in cursor:
            row = self._prepare_row(row, cursor)
            counter['found'] += 1

            room_id = row['MEETING_ROOM_ID'].strip().replace(' ', '-')
            equipment_name = row['EQUIPMENT_NAME']
            building, floor, number = room_id.split('-')

            equipment = self._location.get_equipment_by_name(equipment_name)
            room = Room.find_first(Room.building == building,
                                   Room.floor == floor,
                                   Room.number == number)
            try:
                if not room:
                    raise ValueError('Room not found in Indico DB')
                if not equipment:
                    raise ValueError('Equipment {} not found in Indico DB'.format(equipment_name))
                if not room.available_equipment.filter(EquipmentType.id == equipment.id).count():
                    room.available_equipment.append(equipment)
                    counter['added'] += 1
                    self._logger.info("Added equipment '{}' to room '{}'".format(equipment.name, room.full_name))
                    if equipment == vc_parent:
                        db_vc_equipment = set(room.available_equipment.filter(EquipmentType.parent_id == vc_parent.id))
                        missing_vc_equipment = vc_equipment - db_vc_equipment
                        for eq in missing_vc_equipment:
                            room.available_equipment.append(eq)
                            self._logger.info("Added VC equipment '{}' to room '{}'".format(eq.name, room.full_name))
                foundation_room_equipment[room].append(equipment.id)
            except ValueError as e:
                counter['skipped'] += 1
                self._logger.warning("Skipped room {}: {}".format(room_id, str(e)))

        for room, equipment_types in foundation_room_equipment.iteritems():
            # We handle VC subequipment like equipment that's in the foundation DB since the latter only contains "VC"
            # but no information about the actually available vc equipment...
            foundation_equipment_ids = set(equipment_types) | {eq.id for eq in vc_equipment}
            for equipment in room.available_equipment.filter(~EquipmentType.id.in_(foundation_equipment_ids)):
                self._logger.info("Mismatch: Room {} has equipment {} in Indico DB but not in Foundation"
                                  .format(room.full_name, equipment.name))

        db.session.commit()
        self._logger.info("Equipment associations summary: {} found - {} new added - {} skipped"
                          .format(counter['found'], counter['added'], counter['skipped']))

    def run_all(self, room_name=None):
        with DBMgr.getInstance().global_connection():
            with self.connect_to_foundation() as connection:
                try:
                    self.fetch_rooms(connection, room_name)
                    self.fetch_equipment(connection)
                    self.fetch_room_equipment(connection, room_name)
                    if not room_name:
                        self.fetch_holidays(connection)
                except Exception:
                    self._logger.exception("Synchronization with Foundation failed")
                    raise


class SettingsForm(IndicoForm):
    connection_string = StringField('Foundation DB')


class FoundationSyncPlugin(IndicoPlugin):
    """Foundation Sync

    Synchronizes holidays, rooms and equipment with the CERN Foundation Database.
    """
    configurable = True
    settings_form = SettingsForm

    def add_cli_command(self, manager):
        @manager.option('--room', dest='room_name', help='Synchronize only a given room (e.g. 513 R-055)')
        @with_plugin_context(self)
        def foundationsync(room_name):
            """Synchronize holidays, rooms and equipment with the CERN Foundation Database"""
            db_name = self.settings.get('connection_string')
            if not db_name:
                print 'Foundation DB connection string is not set'
                sys.exit(1)

            if cx_Oracle is None:
                print 'cx_Oracle is not installed'
                sys.exit(1)
            # Log to stdout
            self.logger.addHandler(StreamHandler())
            FoundationSync(db_name, self.logger).run_all(room_name)


@celery.periodic_task(run_every=crontab(minute='0', hour='8'))
def scheduled_update(room_name=None):
    db_name = FoundationSyncPlugin.settings.get('connection_string')
    if not db_name:
        raise RuntimeError('Foundation DB connection string is not set')
    if cx_Oracle is None:
        raise RuntimeError('cx_Oracle is not installed')
    FoundationSync(db_name, FoundationSyncPlugin.logger).run_all(room_name)
