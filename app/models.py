from app import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    abstract = db.Column(db.Text)
    pubdate = db.Column(db.Date)
    volume = db.Column(db.Integer)
    issue = db.Column(db.Integer)
    journal = db.Column(db.Text)
    journalabbr = db.Column(db.Text)
    authors = db.Column(JSON)
    language = db.Column(db.Text)
    issn = db.Column(db.Text)
    keyword = db.Column(ARRAY)
    doc2vec = db.Column(ARRAY)

    def __repr__(self):
        return '<Aticle {}>'.format(self.title)