# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from operator import attrgetter

from flask import request
from markupsafe import escape
from wtforms.fields import BooleanField, SelectField
from wtforms.validators import DataRequired, ValidationError

from indico.core import signals
from indico.core.auth import multipass
from indico.core.config import config
from indico.core.db.sqlalchemy.links import LinkType
from indico.core.plugins import IndicoPlugin
from indico.modules.attachments import Attachment, AttachmentFolder
from indico.modules.categories.models.categories import Category
from indico.modules.events import Event
from indico.modules.events.contributions import Contribution
from indico.modules.events.sessions import Session
from indico.modules.groups import GroupProxy
from indico.util.i18n import make_bound_gettext
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import MultipleItemsField
from indico.web.forms.widgets import SwitchWidget


_ = make_bound_gettext('access_override')


class PluginSettingsForm(IndicoForm):
    enabled = BooleanField(_('Enabled'), widget=SwitchWidget(), description=_('Whether to enable the access overrides'))
    provider = SelectField(_('Group source'), [DataRequired()])
    objects = MultipleItemsField(_('Objects'),
                                 fields=[{'id': 'type', 'caption': _('Type'), 'required': True, 'type': 'select'},
                                         {'id': 'id', 'caption': _('ID'), 'required': True, 'type': 'text',
                                          'coerce': int},
                                         {'id': 'group', 'caption': _('Group'), 'required': True, 'type': 'text'}],
                                 choices={'type': {'category': _('Category'),
                                                   'category_tree': _('Category & Subcategories'),
                                                   'event': _('Event')}},
                                 description=_('Give the specified users full read access to anything inside these '
                                               'events/categories.'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        providers = [p for p in multipass.identity_providers.values() if p.supports_groups]
        choices = []
        if config.LOCAL_GROUPS:
            choices.append(('indico', _('Local Groups')))
        choices += [(p.name, p.title) for p in sorted(providers, key=attrgetter('title'))]
        self.provider.choices = choices

    def validate_objects(self, field):
        if field.errors:
            return
        for entry in field.data:
            try:
                id_ = int(entry['id'])
            except ValueError:
                raise ValidationError(_('IDs must be numeric'))
            if GroupProxy(entry['group'], self.provider.data).group is None:
                raise ValidationError(_('Invalid group: {}').format(escape(entry['group'])))
            if entry['type'] in {'category', 'category_tree'} and not Category.get(id_, is_deleted=False):
                raise ValidationError(_('Invalid category: {}').format(id_))
            if entry['type'] == 'event' and not Event.get(id_, is_deleted=False):
                raise ValidationError(_('Invalid event: {}').format(id_))


class AccessOverridePlugin(IndicoPlugin):
    """Access Override

    Allows providing read access for certain groups to whole categories
    without going through standard ACLs and inheritance.
    """

    configurable = True
    settings_form = PluginSettingsForm
    default_settings = {
        'enabled': False,
        'provider': None,
        'objects': [],
    }

    def init(self):
        super().init()
        for cls in (Category, Event, Session, Contribution, AttachmentFolder, Attachment):
            self.connect(signals.acl.can_access, self._override_can_access, sender=cls)

    def _override_can_access(self, obj_type, obj, user, allow_admin, authorized, **kwargs):
        if authorized is None or authorized:
            # nothing to do if the user has regular access or we haven't checked it yet
            return
        if not allow_admin:
            # we do not override access if we do an explicit check that'd exclude admins
            return
        if user is None:
            # no overrides for unauthenticated users either
            return
        if not self.settings.get('enabled'):
            # overrides are globally disabled
            return
        if self._is_authorized(obj, user):
            if self._should_log_override():
                # the object logged may not necessarily be the one actually accessed if
                # inheritance is used, but we can't avoid this. in any case, with the
                # request log this can be looked up if needed
                self.logger.info('Override access by %r to %r', user, obj)
            return True

    def _is_authorized(self, obj, user):
        candidates = []
        for entry in self.settings.get('objects'):
            group = GroupProxy(entry['group'], self.settings.get('provider'))
            if user not in group:
                continue
            candidates.append({'type': entry['type'], 'id': entry['id']})
        if not candidates:
            return
        event, category = self._lookup_parent(obj)
        for entry in candidates:
            if event and entry['type'] == 'event' and entry['id'] == event.id:
                return True
            elif category and entry['type'] == 'category' and entry['id'] == category.id:
                return True
            elif category and entry['type'] == 'category_tree' and entry['id'] in category.chain_ids:
                return True
        return False

    def _lookup_parent(self, obj):
        if isinstance(obj, Category):
            return None, obj
        elif isinstance(obj, AttachmentFolder) and obj.link_type == LinkType.category:
            return None, obj.category
        elif isinstance(obj, AttachmentFolder):
            return obj.event, obj.event.category
        elif isinstance(obj, Attachment):
            return self._lookup_parent(obj.folder)
        else:
            return obj.event, obj.event.category

    def _should_log_override(self):
        # we log all overrides except for some category metadata loaded in the background
        return request.endpoint not in ('categories.info', 'categories.info_from', 'categories.subcat_info')
