from flask import current_app
from app import db


def add_to_index(index, model):
    # This function adds specific model object to index

    if not current_app.elasticsearch:
        return
    payload = {}
    for field in model.__searchable__:
        payload[field] = getattr(model, field)
    current_app.elasticsearch.index(index=index, doc_type=index, id=model.id,
                                    body=payload)


def remove_from_index(index, model):
    # This function removes specific model object from index

    if not current_app.elasticsearch:
        return
    current_app.elasticsearch.delete(index=index, doc_type=index, id=model.id)


class ESQueryObject:
    # This class is used for query construction and firing them
    # It is important to follow the order of function calls

    def __init__(self, index, model, doctype):
        self.body = {}
        self.index = index

        # This attribute are used to control query structure
        self.search = False
        self.filter = False
        self.doctype = doctype
        self.sort = False
        self.model = model

    # ----------------------------------------------
    #   Methods, used to modify the query
    # ----------------------------------------------

    def search_(self, query, fields=['*'], type_='multi_match'):
        # Convert db.Columns to fields
        fields_list = fields
        if type(fields) == list:
            fields_list = []
            for field in fields:
                fields_list.append(str(field.name))
        print(fields_list)
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
            self.body['sort'] = row
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
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        total = search['hits']['total']
        print(self.body)
        print(self.index)

        return self.fetch_from_db(ids, total)

    def limit_(self, size):
        self.body['size'] = size
        search = current_app.elasticsearch.search(index=self.index, doc_type=self.doctype, body=self.body)
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        total = search['hits']['total']
        return self.fetch_from_db(ids, total)

    def all(self):
        search = current_app.elastivsearch.search(index=self.index, doc_type=self.doctype, body=self.body)
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        total = search['hits']['total']
        return self.fetch_from_db(ids, total)

    # ----------------------------------------------
    #   Method, used to get data from database
    # ----------------------------------------------

    def fetch_from_db(self, ids, total):
        if total == 0:
            return self.model.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return self.model.query.filter(self.model.id.in_(ids)).order_by(
            db.case(when, value=self.model.id)), total


class ESCondition():
    # This class provides important function for .filter method of ESQueryObject

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
