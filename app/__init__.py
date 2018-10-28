from flask import Flask
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_uploads import UploadSet, IMAGES, configure_uploads
from config import Config
from elasticsearch import Elasticsearch
import certifi
import app, os
from flask_login import LoginManager

application = Flask(__name__)
app = application
app.config.from_object(Config)
db = SQLAlchemy(app)
db.configure_mappers()
migrate = Migrate(app, db)
bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = 'login'

photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

app.elasticsearch = Elasticsearch(hosts=[app.config['ELASTICSEARCH_URL']], use_ssl=True, ca_certs=certifi.where()) \
    if app.config['ELASTICSEARCH_URL'] else None

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from app import models

db.init_app(app)

with app.app_context():
    # Extensions like Flask-SQLAlchemy now know what the "current" app
    # is while within this block. Therefore, you can now run........
    db.create_all()

from app import routes, models
