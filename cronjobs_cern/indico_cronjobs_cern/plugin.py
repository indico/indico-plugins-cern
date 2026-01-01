# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from wtforms.fields import EmailField
from wtforms.validators import DataRequired, Email

from indico.core.plugins import IndicoPlugin
from indico.util.string import natural_sort_key
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import EmailListField, MultipleItemsField


def _order_func(object_list):
    return sorted(object_list, key=lambda r: natural_sort_key(r[1].full_name))


class SettingsForm(IndicoForm):
    _fieldsets = [
        ('General settings', ['sender_email']),
        ('Seminar emails', ['seminar_categories', 'seminar_recipients'])
    ]

    sender_email = EmailField('Sender', [DataRequired(), Email()])
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
        'sender_email': 'noreply-indico-team@cern.ch',
        'seminar_categories': set(),
        'seminar_recipients': set()
    }
