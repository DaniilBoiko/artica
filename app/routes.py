import datetime
import json
import math
import requests
from bs4 import BeautifulSoup
from flask import render_template, request, redirect, url_for, jsonify, make_response, session, current_app
from mendeley import Mendeley
from mendeley.session import MendeleySession

from app import app
from app import db
from app import q
from app.models import Article, User, UserDocument, Journal
from app.tools import distance

from app.search import add_to_index


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

    answers, total = Article.search(query, page,
                                    current_app.config['POSTS_PER_PAGE'])
    for answer in answers:
        answer.title = str(answer.title).encode('latin1').decode("utf-8")

    next_url = url_for('search', q=query, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('search', q=query, page=page - 1) \
        if page > 1 else None

    return render_template('search/search.html', title=query, answers=answers, query=query, counts=total,
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
    with app.app_context():
        for i in range(3002, 500000):
            print(i)
            article = Article.query.filter_by(id=i).first()
            print(article.title)
            add_to_index('article', article)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    return render_template('admin/admin.html', title='admin')


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
        article.pubdate = article.pubdate.strftime('Published at %d, %b %Y')
    else:
        article.pubdate = ''

    article.authorlist = []
    try:
        for author in json.loads(article.authors)['Author']:
            article.authorlist.append(author['LastName'] + ' ' + author['ForeName'])
    except:
        article.authorlist.append('')

    return render_template('search/article.html', title=article.title, journal=journal, article=article, query=query)


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

    auth = mendeley.start_authorization_code_flow()
    session['state'] = auth.state

    return render_template('user/login.html', login_url=(auth.get_login_url()))


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
    return redirect('/listDocuments')


@app.route('/listDocuments')
def list_documents():
    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    docs = mendeley_session.documents.list(view='client').items

    return render_template('user/library.html', name=name, docs=docs, title='Library')


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
    if 'token' not in session:
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    document_id = request.args.get('document_id')
    doc = mendeley_session.documents.get(document_id)

    return render_template('metadata.html', doc=doc, name=name, title=doc['title'])


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
        return redirect('/')

    try:
        mendeley_session = get_session_from_cookies()
        name = mendeley_session.profiles.me.display_name
    except:
        return redirect('/logout')

    email = mendeley_session.profiles.me.email

    return render_template('user/account.html', name=name, email=email)


@app.route('/logout')
def logout():
    session.pop('token', None)
    return redirect('/')
