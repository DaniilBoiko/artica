from app import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy_utils import TSVectorType
from sqlalchemy_searchable import SearchQueryMixin,make_searchable
from flask.ext.sqlalchemy import BaseQuery

make_searchable(db.metadata)

class ArticleQuery(BaseQuery, SearchQueryMixin):
    pass

class Article(db.Model):
    query_class = ArticleQuery

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.UnicodeText)
    abstract = db.Column(db.UnicodeText)
    pubdate = db.Column(db.Date)
    volume = db.Column(db.String)
    issue = db.Column(db.String)
    journal = db.Column(db.Text)
    journalabbr = db.Column(db.Text)
    authors = db.Column(JSON)
    language = db.Column(db.String)
    issn = db.Column(db.Text)
    keyword = db.Column(ARRAY(db.String))
    search_vector = db.Column(TSVectorType('title','abstract'))

    def __repr__(self):
        return '<Aticle {}>'.format(self.title)
