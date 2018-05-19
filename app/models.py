from app import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy_utils import TSVectorType
from sqlalchemy_searchable import SearchQueryMixin, make_searchable
from flask.ext.sqlalchemy import BaseQuery

make_searchable(db.metadata)


class ArticleQuery(BaseQuery, SearchQueryMixin):
    pass


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    email = db.Column(db.String)
    last_sync = db.Column(db.Date)
    created = db.Column(db.Date)

    def __repr__(self):
        return '<User {}>'.format(self.last_name)


class UserDocuments(db.model()):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    type = db.Column(db.Text)
    source = db.Column(db.Text)
    year = db.Column(db.Text)
    identifiers = db.Column(db.Text)
    keywords = db.Column(db.Text)
    abstract = db.Column(db.Text)
    authors = db.Column(db.Text)
    user = db.Column(db.Integer)


    def __repr__(self):
        return '<User document {}>'.format(self.title)


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
    search_vector = db.Column(TSVectorType('title', 'abstract'))
    doi = db.Column(db.String)
    doctype = db.Column(db.String)
    crossref = db.Column(db.Text)

    def __repr__(self):
        return '<Aticle {}>'.format(self.title)
