from __future__ import unicode_literals

from wtforms import ValidationError

from indico.core.plugins import IndicoPlugin
from indico.core.settings.converters import SettingConverter
from indico.modules.categories.models.categories import Category
from indico.modules.rb.models.rooms import Room
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoQuerySelectMultipleField, EmailListField, MultipleItemsField


def _order_func(object_list):
    return sorted(object_list, key=lambda r: natural_sort_key(r[1].full_name))


class SettingsForm(IndicoForm):
    _fieldsets = [
        ('Conference room emails', ['rooms', 'reservation_rooms', 'categories', 'conf_room_recipients']),
        ('Startup assistance emails', ['startup_assistance_recipients']),
        ('Seminar emails', ['seminar_categories', 'seminar_recipients'])
    ]

    rooms = IndicoQuerySelectMultipleField('Rooms', get_label='full_name', collection_class=set, render_kw={'size': 20},
                                           modify_object_list=_order_func)
    reservation_rooms = IndicoQuerySelectMultipleField('Reservation rooms', get_label='full_name', collection_class=set,
                                                       render_kw={'size': 20}, modify_object_list=_order_func)
    categories = MultipleItemsField('Categories', fields=[{'id': 'id', 'caption': 'Category ID', 'required': True}])
    conf_room_recipients = EmailListField('Recipients')
    startup_assistance_recipients = EmailListField('Recipients')
    seminar_categories = MultipleItemsField('Seminar categories',
                                            fields=[{'id': 'id', 'caption': 'Category ID', 'required': True}])
    seminar_recipients = EmailListField('Recipients')

    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__(*args, **kwargs)
        self.rooms.query = Room.query
        self.reservation_rooms.query = Room.query

    def validate_categories(self, field):
        ids = [x['id'] for x in field.data]
        if Category.query.filter(Category.id.in_(ids)).count() != len(ids):
            raise ValidationError('Not a valid category ID.')


class RoomConverter(SettingConverter):
    """Convert a list of room objects to a list of room IDs and backwards."""

    @staticmethod
    def from_python(value):
        return sorted(room.id for room in value)

    @staticmethod
    def to_python(value):
        return Room.query.filter(Room.id.in_(value)).all()


class CERNCronjobsPlugin(IndicoPlugin):
    """CERN cronjobs

    This plugin sends email notifications in regular intervals, informing people about upcoming events, events that
    require startup assistance, etc.
    """
    configurable = True
    settings_form = SettingsForm
    settings_converters = {
        'rooms': RoomConverter,
        'reservation_rooms': RoomConverter
    }
    default_settings = {
        'rooms': set(),
        'reservation_rooms': set(),
        'categories': set(),
        'seminar_categories': set(),
        'conf_room_recipients': set(),
        'startup_assistance_recipients': set(),
        'seminar_recipients': set()
    }
