# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import flash, redirect, session
from flask_pluginengine import current_plugin
from werkzeug.exceptions import BadRequest

from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.categories.models.categories import Category
from indico.modules.categories.operations import create_category as _create_category
from indico.modules.events.cloning import get_event_cloners
from indico.modules.events.controllers.base import RHEventBase
from indico.modules.events.operations import clone_event
from indico.web.flask.util import url_for


class RHCloneEvent(RHEventBase):
    """Clone an event to a user's personal category.

    If the category does not exist, it will be created.
    The user has full management rights within the category.
    """
    ALLOW_LOCKED = True

    def _process(self):
        if not (category_id := current_plugin.settings.get('test_category_id')):
            raise BadRequest('No test category ID configured')

        test_category = Category.get(int(category_id))
        user_category = get_user_category(test_category, session.user)

        cloners = {c for c in get_event_cloners().values() if not c.is_internal}
        new_event = clone_event(self.event, n_occurrence=0, start_dt=self.event.start_dt, cloners=cloners,
                                category=user_category, refresh_users=False)

        flash('Event successfully cloned!', 'success')
        return redirect(url_for('event_management.settings', new_event))


def get_user_category(parent, user):
    category = Category.query.filter_by(title=get_category_title(user)).first()
    if category:
        if category.is_deleted:
            category.is_deleted = False
        return category
    return create_category(parent, user)


def create_category(parent, user):
    description = 'This is your own category where you have full management rights. Have fun!'
    category = _create_category(parent, {'title': get_category_title(user), 'description': description})
    category.protection_mode = ProtectionMode.protected
    category.update_principal(user, full_access=True)
    return category


def get_category_title(user):
    return f"{user.full_name}'s category ({user.id})"
