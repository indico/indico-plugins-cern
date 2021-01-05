# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPlugin
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, MultipleItemsField


def _order_func(object_list):
    return sorted(object_list, key=lambda r: natural_sort_key(r[1].full_name))


class SettingsForm(IndicoForm):
    _fieldsets = [
        ('Seminar emails', ['seminar_categories', 'seminar_recipients'])
    ]

    seminar_categories = MultipleItemsField('Seminar categories',
                                            fields=[{'id': 'id', 'caption': 'Category ID', 'required': True}])
    seminar_recipients = EmailListField('Recipients')


class CERNCronjobsPlugin(IndicoPlugin):
    """CERN cronjobs

    This plugin sends email notifications in regular intervals, informing people about upcoming events etc.
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'seminar_categories': set(),
        'seminar_recipients': set()
    }
