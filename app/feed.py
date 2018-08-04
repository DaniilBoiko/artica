import requests, json, numpy, time
from flask import current_app
from app import db, app
from app.models import User, Article
from app.routes import session, redirect, request
from mendeley.session import MendeleySession
from config import Config

def create_initial_feed(mendeley_session, depth=1000, length=20):
    with app.app_context():
        NIKITA_SERVER = 'https://ec2-18-219-191-88.us-east-2.compute.amazonaws.com:8080/get_vectors?articles_id='

        docs = mendeley_session.documents.list(view='client').items

        user_doc_ids = []

        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Indexing user articles', 'Start'))
        for doc in docs:
            document = None

            if doc['identifiers']['doi'] is not None:
                document = Article.query.filter_by(Article.doi == doc['identifiers']['doi']).first()

            if (document is None) or (doc['identifiers']['doi'] is None):

                print("%-15s %-45s %-15s" % (time.strftime('%X'),'Indexing user articles',doc['identifiers']['doi']))
                authors = []
                if doc.authors is not None:
                    for author in doc.authors:
                        authors.append(author.first_name + ' ' + author.last_name)

                new_document = Article(
                    title=doc['title'],
                    abstract=doc['abstract'],
                    authors=authors,
                    doi=doc['identifiers']['doi']
                )

                db.session.add(new_document)
                db.session.commit()

            document = Article.query.filter_by(Article.doi == doc['identifiers']['doi']).first()
            user_doc_ids.append(document.id)
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Indexing user articles', 'End'))

        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Getting artilces_to_check', 'Start'))
        articles_to_check = Article.query.order_by(Article.pubdate).limit(depth)
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Getting artilces_to_check', 'End'))
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Getting fetch_data_for_user', 'Start'))
        fetch_data_for_user = json.loads(str(requests.get(Config.NIKITA_SERVER + str(user_doc_ids)[1:-1]).content))
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Getting fetch_data_for_user', 'End'))

        feed_to_return = []

        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Checking articles', 'Start'))
        i = 0
        for article in articles_to_check:
            score = 0
            i += 1
            print("%-15s %-45s %-15s" % (time.strftime('%X'),'Checking articles', i))

            for user_article in fetch_data_for_user:
                neg_distance = -numpy.linalg.norm(
                    numpy.array(fetch_data_for_user[user_article]) - \
                           numpy.array(article.ml_vector)
                )
                score += numpy.exp(neg_distance)

            print("%-15s %-45s %-15s" % (time.strftime('%X'),'Checking articles', 'Adding to list'))
            if len(feed_to_return) < length:
                feed_to_return.append({'id':article,'score':score})
            else:
                feed_to_return = sorted(feed_to_return, key=lambda k: k['score'])
                if feed_to_return[0]['score'] < score:
                    feed_to_return.pop(0)
                    feed_to_return.append({'id':article,'score':score})
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Checking articles', 'End'))

        return feed_to_return


def get_vectors(ids):
    if type(ids) is not list:
        raise TypeError

    with app.app_context():
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Fetching article vectors', 'Start'))
        fetch_data = requests.get(Config.NIKITA_SERVER + str(ids)[1:-1]).json()
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Fetching article vectors', 'End'))

        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Adding to database', 'Start'))
        for index in fetch_data:
            article = Article.query.get(index)
            article.ml_vector = fetch_data[index]
            db.session.commit()
        print("%-15s %-45s %-15s" % (time.strftime('%X'),'Adding to database', 'End'))



