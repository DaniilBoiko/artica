from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    documents = db.relationship('UserDocument', backref='owner', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    organization = db.Column(db.Text)
    position = db.Column(db.String(120))
    date_of_birth = db.Column(db.Date)
    description = db.Column(db.Text)
    filename = db.Column(db.String(120))
    city = db.Column(db.String(120))
    country = db.Column(db.String(3))

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)



class UserDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    mendeley_id = db.Column(db.String)
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


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    article_id = db.Column(db.String)
    content = db.Column(db.Text)
    published = db.Column(db.DateTime)
    status = db.Column(db.Integer)

    def hide(self):
        self.status = 1
        try:
            db.session.commit()
            return True
        except:
            return False

    def delete(self):
        self.status = 666

        try:
            db.session.commit()
            return True
        except:
            return False

    def __repr__(self):
        return '<Comment {}>'.format(self.id)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    article_id = db.Column(db.String)
    type = db.Column(db.Boolean)

    def __repr__(self):
        return '<Like {}>'.format(self.id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))

