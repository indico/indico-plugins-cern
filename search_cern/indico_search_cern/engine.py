# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2020 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

import re

from flask import redirect
from flask_pluginengine import current_plugin
from werkzeug.urls import url_encode

from indico.core.db import db

from indico_search import SearchEngine


FIELD_MAP = {'title': 'titlereplica',
             'abstract': 'description',
             'author': 'authors',
             'affiliation': 'companies',
             'keyword': 'keywords'}


class CERNSearchEngine(SearchEngine):
    @property
    def use_iframe(self):
        return current_plugin.settings.get('display_mode') == 'iframe'

    def process(self):
        query = self._make_query()
        if not query:
            return None
        elif self.use_iframe:
            return {'iframe_url': self.build_url(k=query)}
        else:
            return redirect(self.build_url(k=query))

    def build_url(self, **query_params):
        params = {'isFrame': unicode(int(self.use_iframe)),
                  'autologin': unicode(int(not current_plugin.only_public)),
                  'showRefiners': '0' if self.obj_type == 'event' else '1',
                  'showDialogs': '0' if self.obj_type == 'event' else '1'}
        return '{}?{}'.format(current_plugin.settings.get('search_url'), url_encode(dict(params, **query_params)))

    def _make_query(self):
        query = []
        # Main search term
        field = self.values['field']
        phrase = self.values['phrase']
        if phrase:
            if field in FIELD_MAP:
                query += self._make_field_query(phrase, FIELD_MAP[field])
            else:
                def replacement(match):
                    field = match.group(2).lower()
                    return match.group(1) + FIELD_MAP[field] + ':'

                pattern = re.compile(r'(-?)({}):'.format('|'.join(FIELD_MAP)), re.IGNORECASE)
                query.append(pattern.sub(replacement, phrase))

        # Date
        query += self._make_date_query()
        # Category/Event
        taxonomy_query = self._make_taxonomy_query()
        if taxonomy_query:
            query.append(taxonomy_query)
        return ' AND '.join(query)

    def _make_field_query(self, phrase, field):
        return ['{}:{}'.format(field, word) for word in phrase.split()]

    def _make_date_query(self):
        start_date = self.values['start_date']
        end_date = self.values['end_date']
        if start_date:
            start_date = start_date.strftime('%Y-%m-%d')
        if end_date:
            end_date = end_date.strftime('%Y-%m-%d')
        query = []
        if start_date:
            query.append('StartDate>={}'.format(start_date))
        if end_date:
            query.append('EndDate<={}'.format(end_date))
        return query

    def _make_taxonomy_query(self):
        if isinstance(self.obj, db.m.Category) and not self.obj.is_root:
            titles = '/'.join(self.obj.chain_titles[1:])
            return 'cerntaxonomy:"Indico/{}"'.format(titles)
        elif isinstance(self.obj, db.m.Event):
            return 'EventID:{}'.format(self.obj.id)
        return ''
