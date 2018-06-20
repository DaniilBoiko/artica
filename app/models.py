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


class Article(db.Model):
    query_class = ArticleQuery

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
    authors = db.Column(ARRAY(db.Integer))
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
    citation_counts = db.Column(db.Integer)

    def __repr__(self):
        return '<Aticle {}>'.format(self.title)


class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    description = db.Column(db.Text)
    subject = db.Column(db.String)
    url = db.Column(db.Text)
    publisher = db.Column(db.String)
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


class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    affilations = db.Column(ARRAY(db.Integer))

    def __repr__(self):
        return '<Author {}>'.format(self.name)


class Affilation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aff = db.Column(db.Text)

    def __repr__(self):
        return '<Author {}>'.format(self.name)


class Cite(db.Model):
    cited_doi = db.Column(db.String)
    citing_doi = db.Column(db.String)
    citing_id = db.Column(db.Integer)
    reference = db.Column(db.Text)

    def __repr__(self):
        return '<Cite {}>'.format(self.reference)
