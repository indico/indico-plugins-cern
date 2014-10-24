from __future__ import unicode_literals

from flask import redirect
from flask_pluginengine import current_plugin
from werkzeug.urls import url_encode

from MaKaC.conference import Category, Conference
from indico_search import SearchEngine


FIELD_MAP = {'title': 'title',
             'abstract': 'description',
             'author': 'author',
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
                  'isDlg': '1',
                  'autologin': unicode(int(not current_plugin.only_public)),
                  'httpsActivation': '1'}
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
                query.append(phrase)
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
        if isinstance(self.obj, Category) and not self.obj.isRoot():
            titles = '/'.join(name.replace('/', '%2F') for name in self.obj.getCategoryPathTitles()[1:])
            return "cerntaxonomy:'Indico/{}'".format(titles)
        elif isinstance(self.obj, Conference):
            return 'EventID:{}'.format(self.obj.id)
        return ''
