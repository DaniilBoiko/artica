import requests, json, numpy, time
from flask import current_app
from app import db, app
from app.models import User, Article, Journal
from app.routes import session, redirect, request
from app.search import ESCondition
from mendeley.session import MendeleySession
from config import Config

es_condition = ESCondition()


def create_initial_feed(mendeley_session, depth=1000, length=20):
    with app.app_context():
        NIKITA_SERVER = 'https://ec2-18-219-191-88.us-east-2.compute.amazonaws.com:8080/get_vectors?articles_id='

        docs = mendeley_session.documents.list(view='client').items

        user_doc_ids = []

        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Indexing user articles', 'Start'))
        for doc in docs:
            document = None
            new_document = None

            total = 0

            if doc.identifiers is not None:
                if 'doi' in doc.identifiers:
                    documents, total = Article.queryES(index='articles', doctype='article'). \
                        filter_(es_condition.eql_('doi', doc.identifiers['doi'])).limit_(1)

            k = False
            if doc.identifiers is None:
                k = True
                doc.identifiers = {'doi': None}
            else:
                if 'doi' not in doc.identifiers:
                    doc.identifiers = {'doi': None}
                    k = True

            if (total == 0) or k:

                print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Indexing user articles', doc.identifiers['doi']))
                authors = []
                if doc.authors is not None:
                    for author in doc.authors:
                        authors.append(author.first_name + ' ' + author.last_name)

                journal = Journal.query.filter_by(name=doc.source).first()
                if journal is None:
                    journal = Journal(name=doc.source)
                    db.session.add(journal)
                    db.session.commit()

                new_document = Article(
                    title=doc.title,
                    abstract=doc.abstract,
                    authors=authors,
                    doi=doc.identifiers['doi'],
                    journal_id=journal.id
                )

                db.session.add(new_document)
                db.session.commit()

                body = {
                    "title": new_document.title,
                    "abstract": new_document.abstract,
                    "doi": new_document.doi,
                    "authors": new_document.authors,
                    "journal_name": journal.name,
                    "pubdate": new_document.pubdate,
                }

                current_app.elasticsearch.index('articles', doc_type='article', id=new_document.id, body=body)

            if new_document is not None:
                if new_document.abstract is not None:
                    user_doc_ids.append(new_document.id)
            else:
                if total != 0:
                    if documents[0].abstract is not None:
                        user_doc_ids.append(documents[0].id)

        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Indexing user articles', 'End'))

        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Getting artilces_to_check', 'Start'))
        articles_to_check, total_articles_to_check = Article.queryES(index='articles', doctype='article').filter_(
            es_condition.exst_('ml_vector'),es_condition.exst_('abstract')).sort_(
            'pubdate', 'desc').limit_(depth)
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Getting artilces_to_check', 'End'))
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Getting fetch_data_for_user', 'Start'))
        fetch_data_for_user = requests.get(Config.NIKITA_SERVER + str(user_doc_ids)[1:-1]).json()
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Getting fetch_data_for_user', 'End'))

        feed_to_return = []

        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Checking articles', 'Start'))
        i = 0
        for article in articles_to_check:
            score = 0
            i += 1
            print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Checking articles', i))

            for user_article in fetch_data_for_user:
                neg_distance = -numpy.linalg.norm(
                    numpy.array(fetch_data_for_user[user_article]) - \
                    numpy.array(article.ml_vector)
                )
                score += numpy.exp(neg_distance)

            if (article.abstract is not None) and (article.abstract != ''):
                if len(feed_to_return) < length:
                    feed_to_return.append({'id': article.id, 'score': score})
                    print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Checking articles', 'Add'))
                else:
                    feed_to_return = sorted(feed_to_return, key=lambda k: k['score'])
                    print(feed_to_return[0]['score'])
                    print(feed_to_return[-1]['score'])
                    print(score)
                    if feed_to_return[0]['score'] < score:
                        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Checking articles', 'Add'))
                        feed_to_return.pop(0)
                        feed_to_return.append({'id': article.id, 'score': score})
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Checking articles', 'End'))
        feed_to_return = sorted(feed_to_return, key=lambda k: k['score'])
        print(feed_to_return)
        return_feed = []
        for item in feed_to_return:
            return_feed.append(int(item['id']))
        print(return_feed)
        return return_feed


def get_vectors(ids):
    if type(ids) is not list:
        raise TypeError

    with app.app_context():
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Fetching article vectors', 'Start'))
        fetch_data = requests.get(Config.NIKITA_SERVER + str(ids)[1:-1]).json()
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Fetching article vectors', 'End'))

        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Adding to database', 'Start'))
        for index in fetch_data:
            article = Article.query.get(index)
            article.ml_vector = fetch_data[index]
            db.session.commit()
        print("%-15s %-45s %-15s" % (time.strftime('%X'), 'Adding to database', 'End'))
