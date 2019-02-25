# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from flask_pluginengine import url_for_plugin
from wtforms import ValidationError

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import SettingConverter
from indico.modules.categories.models.categories import Category
from indico.modules.rb.models.rooms import Room
from indico.modules.rb_new.views.base import WPRoomBookingBase
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, IndicoQuerySelectMultipleField, MultipleItemsField
from indico.web.menu import TopMenuItem

from indico_room_assistance import _
from indico_room_assistance.blueprint import blueprint
from indico_room_assistance.models.room_assistance_requests import RoomAssistanceRequest


def _order_func(object_list):
    return sorted(object_list, key=lambda r: natural_sort_key(r[1].full_name))


class RoomAssistanceForm(IndicoForm):
    _fieldsets = [
        ('Conference room emails', ['rooms', 'reservation_rooms', 'categories', 'conf_room_recipients']),
        ('Startup assistance emails', ['room_assistance_recipients', 'rooms_with_assistance']),
    ]

    rooms = IndicoQuerySelectMultipleField('Rooms', get_label='full_name', collection_class=set, render_kw={'size': 20},
                                           modify_object_list=_order_func)
    reservation_rooms = IndicoQuerySelectMultipleField('Reservation rooms', get_label='full_name', collection_class=set,
                                                       render_kw={'size': 20}, modify_object_list=_order_func)
    categories = MultipleItemsField('Categories', fields=[{'id': 'id', 'caption': 'Category ID', 'required': True}])
    conf_room_recipients = EmailListField('Recipients')

    room_assistance_recipients = EmailListField(_('Recipients'))
    rooms_with_assistance = IndicoQuerySelectMultipleField('Rooms', get_label='full_name', collection_class=set,
                                                           render_kw={'size': 20}, modify_object_list=_order_func)

    def __init__(self, *args, **kwargs):
        super(RoomAssistanceForm, self).__init__(*args, **kwargs)
        self.rooms.query = Room.query
        self.reservation_rooms.query = Room.query
        self.rooms_with_assistance.query = Room.query

    def validate_categories(self, field):
        ids = [x['id'] for x in field.data]
        if Category.query.filter(Category.id.in_(ids)).count() != len(ids):
            raise ValidationError('Not a valid category ID.')


class RoomConverter(SettingConverter):
    @staticmethod
    def from_python(value):
        return sorted(room.id for room in value)

    @staticmethod
    def to_python(value):
        return Room.query.filter(Room.id.in_(value)).all()


class RoomAssistanceRequestPlugin(IndicoPlugin):
    """Room assistance request

    This plugin sends email notifications with information about reservations
    for which their creators asked for assistance with the room.
    """

    configurable = True
    settings_form = RoomAssistanceForm
    settings_converters = {
        'rooms': RoomConverter,
        'reservation_rooms': RoomConverter,
        'rooms_with_assistance': RoomConverter
    }
    default_settings = {
        'rooms': set(),
        'reservation_rooms': set(),
        'categories': set(),
        'conf_room_recipients': set(),
        'room_assistance_recipients': [],
        'rooms_with_assistance': set(),
    }

    def init(self):
        super(RoomAssistanceRequestPlugin, self).init()
        self.connect(signals.menu.items, self._extend_services_menu, sender='top-menu')
        self.connect(signals.rb.booking_created, self._create_request_if_necessary)
        self.inject_bundle('react.js', WPRoomBookingBase)
        self.inject_bundle('semantic-ui.js', WPRoomBookingBase)
        self.inject_bundle('room_assistance.js', WPRoomBookingBase)
        self.inject_bundle('room_assistance.css', WPRoomBookingBase)

    def get_blueprints(self):
        return blueprint

    def _extend_services_menu(self, reservation, **kwargs):
        return TopMenuItem('services-cern-room-assistance', _('Room assistance'),
                           url_for_plugin('room_assistance.request_list'), section='services')

    def _create_request_if_necessary(self, reservation, extra_fields, **kwargs):
        if not extra_fields:
            return

        should_create_request = extra_fields.get('notification_for_assistance')
        if not should_create_request:
            return

        reservation.room_assistance_request = RoomAssistanceRequest()
        db.session.flush()
