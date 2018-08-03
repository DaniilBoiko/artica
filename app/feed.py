import requests, json, numpy
from flask import current_app
from app import db, app
from app.models import User, Article
from app.routes import session, get_session_from_cookies, redirect, request


def create_initial_feed(user_id, depth=1000, length=20):
    with app.app_context():
        NIKITA_SERVER = 'https://ec2-18-219-191-88.us-east-2.compute.amazonaws.com:8080/get_vectors'

        user = User.query.get(user_id)
        if user is None:
            return

        if 'token' not in session:
            return redirect('/')

        try:
            mendeley_session = get_session_from_cookies()
            name = mendeley_session.profiles.me.display_name
        except:
            return redirect('/logout')

        docs = mendeley_session.documents.list(view='client').items

        user_doc_ids = []

        for doc in docs:
            document = None

            if doc['identifiers']['doi'] is not None:
                document = Article.query.filter_by(Article.doi == doc['identifiers']['doi']).first()

            if (document is None) or (doc['identifiers']['doi'] is None):

                print('Firing printing')
                authors = []
                if document.authors is not None:
                    for author in document.authors:
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

        articles_to_check = Article.query.order_by(Article.pubdate).limit(depth)

        article_ids = []
        for article in articles_to_check:
            article_ids.append(article.id)

        fetch_data_for_checking = json.loads(requests.get(NIKITA_SERVER + str(article_ids)[1:-1]).content)
        fetch_data_for_user = json.loads(requests.get(NIKITA_SERVER + str(user_doc_ids)[1:-1]).content)

        feed_to_return = []

        for article in fetch_data_for_checking:
            score = 0
            for user_article in fetch_data_for_user:
                neg_distance = -numpy.linalg.norm(
                    numpy.array(fetch_data_for_user[user_article]) - \
                           numpy.array(fetch_data_for_checking[article])
                )
                score += numpy.exp(neg_distance)

            if length(feed_to_return) < length:
                feed_to_return.append({'id':article,'score':score})
            else:
                feed_to_return = sorted(feed_to_return, key=lambda k: k['score'])
                if feed_to_return[0]['score'] < score:
                    feed_to_return.pop(0)
                    feed_to_return.append({'id':article,'score':score})

        return feed_to_return