import datetime
import json
import math
import requests
import wikipedia
from bs4 import BeautifulSoup
from flask import render_template, request, redirect, url_for, session, current_app
from elasticsearch import client

from mendeley import Mendeley
from mendeley.session import MendeleySession

from app import app
from app import db
from app import q
from app.models import Article, User, UserDocument, Journal
from app.tools import distance
from app.search import ESCondition
from app.feed import create_initial_feed, get_vectors

from app.search import add_to_index
from sqlalchemy import desc


def get_session_from_cookies():
    return MendeleySession(mendeley, session['token'])


mendeley = Mendeley('5691', 'Q87rg9xQ58L2HDav', 'http://ec2-18-220-156-220.us-east-2.compute.amazonaws.com:8080/oauth')


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query', type=str)
    if (query is None) or len(query) < 5:
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)

    answers, total = Article.queryES(index='articles', doctype='article'). \
        search_(query, fields=[Article.title, Article.abstract]).paginate(
        int(page),
        int(current_app.config['POSTS_PER_PAGE'])
    )

    articles = []

    for article in answers:
        article.title = str(article.title).encode('latin1').decode("utf-8")

        if article.pubdate is not None:
            pub_date = article.pubdate.strftime('Published at %d, %b %Y')
        else:
            pub_date = ''

        if article.journal_id is not None:
            journal_name = Journal.query.get_or_404(article.journal_id).name
        else:
            journal_name = ''

        articles.append({
            'id': article.id,
            'title': str(article.title).encode('latin1').decode("utf-8"),
            'abstract': article.abstract,
            'authors': article.authors,
            'pub_date': pub_date,
            'journal_name': journal_name,
            'src': article.src,
            'journal_id': article.journal_id
        })

    next_url = url_for('search', q=query, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('search', q=query, page=page - 1) \
        if page > 1 else None

    return render_template('search/search.html', title=query, answers=articles, query=query, counts=total,
                           npages=int(math.ceil(total / current_app.config['POSTS_PER_PAGE'])),
                           page=page)


@app.route('/es_reindex')
def es_reindex():
    job = q.enqueue_call(
        func=es_reindex, args=(), result_ttl=50000, timeout=360000
    )
    print(job.get_id())

    return redirect(url_for('index'))


def es_reindex():
    current_app.elasticsearch.indices.create(index='articles',
                                             body={
                                                 "settings": {
                                                     "number_of_shards": 1
                                                 },
                                                 "mappings": {
                                                     "article": {
                                                         "properties": {
                                                             "title": {"type": "text", "analyzer": "english"},
                                                             "abstract": {"type": "text", "analyzer": "english"},
                                                             "doi": {"type": "keyword"},
                                                             "authors": {"type": "keyword"},
                                                             "journal_name": {"type": "keyword"},
                                                             "pubdate": {
                                                                 "type": "date"
                                                             }
                                                         }
                                                     }
                                                 }
                                             }
                                             )

    with app.app_context():
        journal_id = 100000000000
        journal_name = ''
        for i in range(1, 500000):
            article = Article.query.get_or_404(i)
            print(i)

            if journal_id != article.journal_id:
                journal_name = Journal.query.get_or_404(article.journal_id).name
                journal_id = article.journal_id

            body = {
                "title": article.title,
                "abstract": article.abstract,
                "doi": article.doi,
                "authors": article.authors,
                "journal_name": journal_name,
                "pubdate": article.pubdate
            }

            current_app.elasticsearch.index('articles', doc_type='article', id=article.id, body=body)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    return render_template('admin/admin.html', title='admin')


@app.route('/journal', methods=['GET'])
def journal():
    id = request.args.get('id', type=int)
    query = request.args.get('query', default='', type=str)

    if id is None:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    journal = Journal.query.get_or_404(id)

    if journal.name is not None:
        journal.name = journal.name
    else:
        journal.title = ''

    summary = wikipedia.summary(journal.name + ' (journal)')
    if summary is None:
        summary = wikipedia.summary(journal.name)

    if summary is not None:
        if 'journal' not in summary.split('.')[0]:
            summary = None
    '''
    n_issue = []
    n_volumes = Article.query.filter_by(journal_id=journal.id).order_by(Article.id).first().volume
    for i in range(1, int(n_volumes) + 1):
        n_issue.append(int(Article.query.filter(Article.journal_id == journal.id, Article.volume == str(i)).order_by(
            Article.id).first().issue))
    print(n_issue)
    '''
    es_condition = ESCondition()

    last_published, total = Article.queryES(index='articles', doctype='article'). \
        filter_(es_condition.eql_('journal_name', journal.name)).sort_('pubdate', 'desc').limit_(6)

    # last_published = Article.query.filter_by(journal_id=journal.id).order_by(desc(Article.pubdate)).limit(5).all()

    return render_template('search/journal.html', title=journal.name, journal=journal, query=query, summary=summary,
                           n_issue=[], last_published=last_published)


@app.route('/article', methods=['GET'])
def article():
    id = request.args.get('id')

    if id is None:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    article = Article.query.get_or_404(id)
    journal = Journal.query.get_or_404(article.journal_id)

    if article.title is not None:
        article.title = article.title
    else:
        article.title = ''

    if article.abstract is not None:
        article.abstract = article.abstract
    else:
        article.abstract = ''

    if article.pubdate is not None:
        pub_date = article.pubdate.strftime('Published at %d, %b %Y')
    else:
        pub_date = ''

    return render_template('search/article.html', title=article.title, journal=journal, article=article, query=query,
                           pub_date=pub_date)


@app.route("/add_data", methods=['GET'])
def add_data():
    id = request.args.get('id')

    if id is None:
        return "ERROR", 202

    doi = request.args.get('doi', '')
    doctype = request.args.get('doctype', '')
    crossref = request.args.get('crossref', '')
    title = request.args.get('title', '')

    article = Article.query.get_or_404(int(id))

    if article.title is not None:
        title1 = article.title[2:]
        title1 = article.title[:-1]
        if article.title[0] == '[':
            title1 = article.title[1:]
            title1 = str(article.title[:-2]) + '.'
    else:
        title1 = ' '

    if distance(title1[0:-1].lower(), title.lower()) < 6:
        article.doi = doi
        article.doctype = doctype
        article.crossref = crossref

        db.session.commit()

    return "OK", 200


# Mendeley

@app.route('/login')
def login():
    if 'token' in session:
        return redirect('/listDocuments')

    query = request.args.get('query', '')

    auth = mendeley.start_authorization_code_flow()
    session['state'] = auth.state

    return render_template('user/login.html', login_url=(auth.get_login_url()), query=query)


@app.route('/oauth')
def auth_return():
    auth = mendeley.start_authorization_code_flow(state=session['state'])
    mendeley_session = auth.authenticate(request.url)

    session.clear()
    session['token'] = mendeley_session.token

    if User.query.filter_by(email=mendeley_session.profiles.me.email).first() is None:
        new_user = User(mendeley_id=mendeley_session.profiles.me.id,
                        first_name=mendeley_session.profiles.me.first_name,
                        last_name=mendeley_session.profiles.me.last_name,
                        display_name=mendeley_session.profiles.me.display_name,
                        email=mendeley_session.profiles.me.email,
                        created=datetime.datetime.today())
        db.session.add(new_user)
        db.session.commit()
        if mendeley_session.documents.list(view='client').items is not None:
            for document in mendeley_session.documents.list(view='client').items:

                authors = []
                if document.authors is not None:
                    for author in document.authors:
                        authors.append(author.first_name + ' ' + author.last_name)

                user_doc = UserDocument(mendeley_id=document.id,
                                        title=document.title,
                                        type=document.type,
                                        source=document.source,
                                        year=document.year,
                                        identifiers=document.identifiers,
                                        keywords=document.keywords,
                                        abstract=document.abstract,
                                        authors=authors,
                                        user=User.query.filter_by(email=mendeley_session.profiles.me.email).first().id)
                db.session.add(user_doc)
                db.session.commit()

        create_initial_feed(User.query.filter_by(email=mendeley_session.profiles.me.email).first().id)

    return redirect('/listDocuments')


@app.route('/listDocuments')
def list_documents():
    query = request.args.get('query', '')

    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    docs = mendeley_session.documents.list(view='client').items

    return render_template('user/library.html', name=name, docs=docs, title='Library', query=query)


@app.route('/download')
def download():
    if 'token' not in session:
        return redirect('/')

    mendeley_session = get_session_from_cookies()

    document_id = request.args.get('document_id')
    doc = mendeley_session.documents.get(document_id)
    doc_file = doc.files.list().items[0]

    return redirect(doc_file.download_url)


@app.route('/document')
def get_document():
    query = request.args.get('query', '')

    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    document_id = request.args.get('document_id')
    doc = mendeley_session.documents.get(document_id)

    return render_template('metadata.html', doc=doc, name=name, title=doc['title'], query=query)


@app.route('/metadataLookup')
def metadata_lookup():
    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    doi = request.args.get('doi')
    doc = mendeley_session.catalog.by_identifier(doi=doi)

    return render_template('metadata.html', doc=doc, name=name, title=doc['title'])


@app.route('/account')
def account():
    if 'token' not in session:
        return render_template('technical_pages/login_wall.html')

    query = request.args.get('query', '')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    email = mendeley_session.profiles.me.email

    return render_template('user/account.html', name=name, email=email, query=query)


@app.route('/logout')
def logout():
    query = request.args.get('query', '')

    session.pop('token', None)
    return redirect('/', query=query)


@app.route('/feed')
def feed():
    query = request.args.get('query', '')

    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    user = User.query.filter_by(email=mendeley_session.profiles.me.email).first()

    articles = []
    for id in user.feed:
        article = Article.query.get(id)

        article.title = str(article.title).encode('latin1').decode("utf-8")

        if article.pubdate is not None:
            pub_date = article.pubdate.strftime('Published at %d, %b %Y')
        else:
            pub_date = ''

        if article.journal_id is not None:
            journal_name = Journal.query.get_or_404(article.journal_id).name
        else:
            journal_name = ''

        articles.append({
            'id': article.id,
            'title': str(article.title).encode('latin1').decode("utf-8"),
            'abstract': article.abstract,
            'authors': article.authors,
            'pub_date': pub_date,
            'journal_name': journal_name,
            'src': article.src,
            'journal_id': article.journal_id
        })

    return render_template('feed/feed.html', title='Feed', query=query, articles=articles)


@app.route('/ml/index')
def ml_index():
    start = request.args.get('start')
    end = request.args.get('end')

    batch_size = 0
    article_ids = []
    for i in range(start, end + 1):
        print(i)
        if (batch_size > 1000) or (i == end):
            get_vectors(article_ids)
            article_ids = 0
            batch_size = 0
        else:
            article = Article.query.get(i)
            if article is not None:
                article_ids.append(article.id)
            batch_size += 1
