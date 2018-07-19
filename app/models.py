from app import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy_utils import TSVectorType
from sqlalchemy_searchable import SearchQueryMixin
from flask.ext.sqlalchemy import BaseQuery

# --------------------------------------------------------
#                  Elastic Search
# --------------------------------------------------------

from app.search import add_to_index, remove_from_index, ESQueryObject


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page, suggestion=False):
        ids, total = query_index(cls.__name__.lower(), expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def queryES(cls):
        return ESQueryObject(cls.__name__.lower(), cls)

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__name__.lower(), obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__name__.lower(), obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__name__.lower(), obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__name__.lower(), obj)


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mendeley_id = db.Column(db.String)
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    display_name = db.Column(db.String)
    email = db.Column(db.String)
    last_sync = db.Column(db.DateTime)
    created = db.Column(db.DateTime)

    def __repr__(self):
        return '<User {}>'.format(self.last_name)


class UserDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mendeley_id = db.Column(db.String)
    title = db.Column(db.Text)
    type = db.Column(db.Text)
    source = db.Column(db.Text)
    year = db.Column(db.Text)
    identifiers = db.Column(db.JSON)
    keywords = db.Column(db.JSON)
    abstract = db.Column(db.Text)
    authors = db.Column(db.JSON)
    user = db.Column(db.Integer)

    def __repr__(self):
        return '<User document {}>'.format(self.title)


class Article(SearchableMixin, db.Model):
    __searchable__ = ['title', 'abstract']

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String)
    pubmed_id = db.Column(db.Integer)
    arxiv_id = db.Column(db.String)
    title = db.Column(db.UnicodeText)
    abstract = db.Column(db.UnicodeText)
    src = db.Column(db.String)
    pages = db.Column(db.String)
    pubdate = db.Column(db.Date)
    volume = db.Column(db.String)
    issue = db.Column(db.String)
    journal_id = db.Column(db.Integer)
    journalabbr = db.Column(db.Text)
    authors = db.Column(JSON)
    language = db.Column(db.String)
    issn = db.Column(db.Text)
    isbn = db.Column(db.Text)
    technical_info = db.Column(db.String)
    keyword = db.Column(ARRAY(db.String))
    search_vector = db.Column(TSVectorType('title', 'abstract'))
    doi = db.Column(db.String)
    doctype = db.Column(db.String)
    crossref = db.Column(db.Text)
    meta_data = db.Column(db.Text)

    def __repr__(self):
        return '<Aticle {}>'.format(self.title)


class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    description = db.Column(db.Text)
    subject = db.Column(db.String)
    url = db.Column(db.Text)
    last_fetched = db.Column(db.DateTime)
    last_volume = db.Column(db.String)
    last_issue = db.Column(db.String)
    language = db.Column(db.String)
    issn = db.Column(db.Text)
    isbn = db.Column(db.Text)
    technical_info = db.Column(db.String)
    keyword = db.Column(ARRAY(db.String))
    job_id = db.Column(db.String)

    def __repr__(self):
        return '<Journal {}>'.format(self.name)
