# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import functools

from indico.core.db.sqlalchemy import db
from indico.util.string import format_repr


class GlobalIdMap(db.Model):
    __tablename__ = 'id_map'
    __table_args__ = {'schema': 'plugin_global'}

    col = db.Column(db.String, primary_key=True)
    local_id = db.Column(db.Integer, primary_key=True)
    global_id = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return format_repr(self, 'id', 'col', _repr=self.global_id)

    @classmethod
    @functools.cache
    def get_global_id(cls, col: str, local_id: int) -> int:
        """Get the Indico Global ID for a given col and id."""
        return db.session.query(cls.global_id).filter_by(col=col, local_id=local_id).scalar()

    @classmethod
    def create(cls, col: str, local_id: int, global_id: int) -> None:
        """Create a new mapping."""
        db.session.add(cls(col=col, local_id=local_id, global_id=global_id))
