from app import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy_searchable import make_searchable
from sqlalchemy_utils import TSVectorType

make_searchable()

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    abstract = db.Column(db.Text)
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
