from flask import Flask
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from rq import Queue

from config import Config
from ..worker import conn


application = Flask(__name__)
app = application
app.config.from_object(Config)
db = SQLAlchemy(app)
db.configure_mappers()
migrate = Migrate(app, db)
bootstrap = Bootstrap(app)
q = Queue(connection=conn)

from app import models

db.init_app(app)
with app.app_context():
    # Extensions like Flask-SQLAlchemy now know what the "current" app
    # is while within this block. Therefore, you can now run........
    db.create_all()

from app import routes, models
