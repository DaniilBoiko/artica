from flask import current_app
from app import db

def add_to_index(index, model):
    if not current_app.elasticsearch:
        return
    payload = {}
    for field in model.__searchable__:
        payload[field] = getattr(model, field)
    current_app.elasticsearch.index(index=index, doc_type=index, id=model.id,
                                    body=payload)


def remove_from_index(index, model):
    if not current_app.elasticsearch:
        return
    current_app.elasticsearch.delete(index=index, doc_type=index, id=model.id)


def query_index(index, query=None, page=1, per_page=25, filters=None, sort=None):
    if not current_app.elasticsearch:
        return [], 0

    body = {
        'query':
            {"bool":
                 {"must":
                      {'multi_match':
                           {'query': query, 'fields': ['*']}
                       }
                  }
             },
        'from': (page - 1) * per_page,
        'size': per_page
    }

    if sort is not None:
        body['sort'] = sort

    if filter is not None:
        body['query']['bool']['must']['filter'] = filters

    if query is not None:
        if type(query) == str:
            body['query']['bool']['must'] = {'multi_match':
                                                 {'query': query, 'fields': ['*']}
                                             }
        else:
            body['query']['bool']['must'] = query

    search = current_app.elasticsearch.search(
        index=index, doc_type=index,
        body=body)
    ids = [int(hit['_id']) for hit in search['hits']['hits']]
    return ids, search['hits']['total']


class ESQueryObject:
    def __init__(self, index, model):
        self.body = {}
        self.index = index
        self.query = False
        self.filter = False
        self.sort = False
        self.model = model

    def query_function(self, type, query, fields):
        if not self.query:
            self.body['query'] = {"bool":
                                      {"must":
                                           {type:
                                                {'query': query, 'fields': fields}
                                            }
                                       }
                                  }
            self.query = True
            return self
        else:
            raise Exception('Already quered')

    def filter(self, *conditions):
        if not self.query:
            for condition in conditions:
                self.body['query']['bool']['must']['filter'] = condition
            return self
        else:
            raise Exception('Already filtered')

    def sort(self, row, type):
        if not self.sort:
            self.body['sort'] = row
            return self
        else:
            raise Exception('Already sorted')

    def paginate(self, page, per_page):
        self.body['from'] = (page - 1) * per_page
        self.body['size'] = per_page
        print(self.body)
        search = current_app.elasticsearch.search(index=self.index, doc_type=self.index, body=self.body)
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        total  = search['hits']['total']

        if total == 0:
            return self.model.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return self.model.query.filter(self.model.id.in_(ids)).order_by(
            db.case(when, value=self.model.id)), total

    def all(self):
        search = current_app.elastivsearch.search(index=self.index, doc_type=self.index, body=self.body)
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        return ids, search['hits']['total']


def suggest_index(index, query, size, per_page):
    if not current_app.elasticsearch:
        return [], 0

    search = current_app.elasticsearch.search(
        index=index, doc_type=index,
        body={'suggest': {'suggest': {'prefix': query, 'completion': {'field': 'suggest'}}}})
    ids = [int(hit['_id']) for hit in search['suggest']['suggest']]
    return ids, search['hits']['total']
