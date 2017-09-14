from __future__ import unicode_literals

from flask import current_app, jsonify, request
from sqlalchemy.orm import load_only
from werkzeug.exceptions import Unauthorized

from indico.legacy.webinterface.rh.base import RH
from indico.modules.categories import Category


class RHCategoriesJSON(RH):
    """Provide category information for CERN search"""

    def _checkProtection(self):
        from indico_livesync_cern.plugin import CERNLiveSyncPlugin
        auth = request.authorization
        username = CERNLiveSyncPlugin.settings.get('username')
        password = CERNLiveSyncPlugin.settings.get('password')
        if not auth or not auth.password or auth.username != username or auth.password != password:
            response = current_app.response_class('Authorization required', 401,
                                                  {'WWW-Authenticate': 'Basic realm="Indico - CERN Search"'})
            raise Unauthorized(response=response)

    def _process(self):
        query = (Category.query
                 .filter_by(is_deleted=False)
                 .options(load_only('id', 'title'))
                 .order_by(Category.id).all())
        return jsonify(categories=[{'id': c.id, 'title': c.title} for c in query])
