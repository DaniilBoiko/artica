import os
basedir = os.path.abspath(os.path.dirname(__file__))

POSTGRES = {
    'user': 'artica',
    'pw': 'keklolkek',
    'db': 'artica',
    'host': 'artica.caur5thdijuo.us-east-2.rds.amazonaws.com',
    'port': '5432',
}

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = 'postgresql://%(user)s:%(pw)s@%(host)s:%(port)s/%(db)s' % POSTGRES
    SQLALCHEMY_TRACK_MODIFICATIONS = False