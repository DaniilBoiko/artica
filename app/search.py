from flask import current_app
from app import db


class ESQueryObject:
    # This class is used for query construction and firing them
    # It is important to follow the order of function calls

    def __init__(self, index, doctype):
        self.body = {}
        self.index = index

        # This attribute are used to control query structure
        self.search = False
        self.filter = False
        self.doctype = doctype
        self.sort = False

    # ----------------------------------------------
    #   Methods, used to modify the query
    # ----------------------------------------------

    def search_(self, query, fields=['*'], type_='multi_match'):
        fields_list = fields

        # Fire query
        if not self.search:
            self.body['query'] = {"bool":
                {"must":
                    [
                        {type_:
                             {'query': query, 'fields': fields_list}
                         }
                    ]
                }
            }

            self.search = True
            return self
        else:
            raise Exception('Already quered')

    def filter_(self, *conditions):
        if not self.filter:
            if not self.search:
                self.body['query'] = {"bool":
                                          {'filter': []}
                                      }
            for condition in conditions:
                self.body['query']['bool']['filter'].append(condition)
            return self
        else:
            raise Exception('Already filtered')

    def sort_(self, row, type):
        if not self.sort:
            self.body['sort'] = [{row: type}]
            return self
        else:
            raise Exception('Already sorted')

    def suggest_(self, query, size):
        if not current_app.elasticsearch:
            return [], 0

        search = current_app.elasticsearch.search(
            index=self.index, doc_type=self.index,
            body={'suggest': {'suggest': {'prefix': query, 'completion': {'field': 'suggest'}}}})
        ids = [int(hit['_id']) for hit in search['suggest']['suggest']]
        return self.fetch_from_db(ids, search['hits']['total'])

    # ----------------------------------------------
    #   Methods, used to limit the query size
    # ----------------------------------------------

    def aggregate(self, field):
        return self

    def paginate(self, page, per_page):
        self.body['from'] = (page - 1) * per_page
        self.body['size'] = per_page
        search = current_app.elasticsearch.search(index=self.index, doc_type=self.doctype, body=self.body)
        data = [hit['_source'] for hit in search['hits']['hits']]
        total = search['hits']['total']
        return data, total

    def limit_(self, size):
        self.body['size'] = size
        search = current_app.elasticsearch.search(index=self.index, doc_type=self.doctype, body=self.body)
        data = [hit['_source'] for hit in search['hits']['hits']]
        total = search['hits']['total']
        return data, total

    def all(self):
        search = current_app.elastivsearch.search(index=self.index, doc_type=self.doctype, body=self.body)
        data = [hit['_source'] for hit in search['hits']['hits']]
        total = search['hits']['total']
        return data, total


class ESCondition():
    # This class provides important function for .filter method of ESQueryObject
    def exst_(self, field):
        return {'exists': {"field": field}}

    def btw_(self, field, start, end, strict=False):
        return {'range', {field: {'gte': start, 'lte': end}}} if not strict else {'range', {
            'field': {'gt': start, 'lte': end}}}

    def grt_(self, field, value, strict=False):
        return {'range', {field: {'gte': value}}} if not strict else {'range', {
            'field': {'gt': value}}}

    def lss_(self, field, value, strict=False):
        return {'range', {field: {'lte': value}}} if not strict else {'range', {
            'field': {'lt': value}}}

    def eql_(self, field, value):
        return {'term': {field: value}}
