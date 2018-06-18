import collections
import datetime
import json
import math
import re
import requests
import xmltodict
import time
from bs4 import BeautifulSoup
from flask import render_template, request, redirect, url_for, jsonify, make_response, session
from mendeley import Mendeley
from mendeley.session import MendeleySession
from sqlalchemy import func,between
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text
from sqlalchemy_searchable import search

from app import app
from app import db
from app import q, Job, conn
from app.models import Article, User, UserDocument, Journal

count_pattern = re.compile(r'rows=(\d+)')


def extract_analyze_count(rows):
    for row in rows:
        match = count_pattern.search(row[0])
        if match:
            return int(match.groups()[0])


def count_estimate(query, session, threshold=None):
    rows = session.execute(explain(query)).fetchall()
    count = extract_analyze_count(rows)
    if threshold is not None and count < threshold:
        return query.count()
    return count


def get_session_from_cookies():
    return MendeleySession(mendeley, session['token'])


mendeley = Mendeley('5691', 'Q87rg9xQ58L2HDav', 'http://ec2-18-220-156-220.us-east-2.compute.amazonaws.com:8080/oauth')


class explain(Executable, ClauseElement):
    def __init__(self, stmt, analyze=False):
        self.statement = _literal_as_text(stmt)
        self.analyze = analyze
        # helps with INSERT statements
        self.inline = getattr(stmt, 'inline', None)


def get_count(q):
    count_q = q.statement.with_only_columns([func.count()]).order_by(None)
    count = q.session.execute(count_q).scalar()
    return count


@compiles(explain, 'postgresql')
def pg_explain(element, compiler, **kw):
    text = 'EXPLAIN '
    if element.analyze:
        text += 'ANALYZE '
    text += compiler.process(element.statement, **kw)
    return text


def parseXMLs():
    for i in range(1, 2):
        print(i)
        with open('/data/ftp.ncbi.nlm.nih.gov/pubmed/baseline/pubmed18n{0}.xml'.format(str('{:04d}'.format(i)))) as fd:
            doc = xmltodict.parse(fd.read())
            for article in doc['PubmedArticleSet']['PubmedArticle']:
                try:
                    title = str(article['MedlineCitation']['Article']['ArticleTitle'].encode(encoding="UTF-8"))
                except:
                    title = None

                try:
                    abstract = str(
                        article['MedlineCitation']['Article']['Abstract']['AbstractText'].encode(encoding="UTF-8"))
                    if type(abstract[0]) is collections.OrderedDict:
                        abstract = str(abstract['#text'].encode(encoding="UTF-8"))
                except:
                    abstract = None

                try:
                    year = int(article['MedlineCitation']['DateCompleted']['Year'])
                    month = int(article['MedlineCitation']['DateCompleted']['Month'])
                    day = int(article['MedlineCitation']['DateCompleted']['Day'])
                    pubdate = datetime.date(year=year, month=month, day=day)
                except:
                    pubdate = None

                try:
                    volume = article['MedlineCitation']['Article']['Journal']['JournalIssue']['Volume']
                except:
                    volume = None

                try:
                    issue = article['MedlineCitation']['Article']['Journal']['JournalIssue']['Issue']
                except:
                    issue = None

                try:
                    journal = article['MedlineCitation']['Article']['Journal']['Title']
                except:
                    journal = None

                try:
                    journalabbr = article['MedlineCitation']['Article']['Journal']['ISOAbbreviation']
                except:
                    journalabbr = None

                try:
                    authors = json.dumps(article['MedlineCitation']['Article']['AuthorList'])
                except:
                    authors = None

                try:
                    language = article['MedlineCitation']['Article']['Language']
                except:
                    language = None

                try:
                    keywords = []
                    for topic in article['MedlineCitation']['MeshHeadingList']['MeshHeading']:
                        keywords.append(topic['DescriptorName']['#text'])
                except:
                    keywords = None

                try:
                    issn = article['MedlineCitation']['Article']['Journal']['ISSN']['#text']
                except:
                    issn = None

                try:
                    pubmed_id = article['MedlineCitation']['PMID']
                except:
                    pubmed_id = None

                article = Article(title=title, abstract=abstract, pubdate=pubdate, volume=volume, issue=issue,
                                  journal=journal, journalabbr=journalabbr, authors=authors, language=language,
                                  keyword=keywords, issn=issn, source='pubmed', pubmed_id=pubmed_id, technical_info=i)
                db.session.add(article)
                db.session.commit()
    return 'success'


def distance(a, b):
    "Calculates the Levenshtein distance between a and b."
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a, b = b, a
        n, m = m, n

    current_row = range(n + 1)  # Keep current and previous row, not entire matrix
    for i in range(1, m + 1):
        previous_row, current_row = current_row, [i] + [0] * n
        for j in range(1, n + 1):
            add, delete, change = previous_row[j] + 1, current_row[j - 1] + 1, previous_row[j - 1]
            if a[j - 1] != b[i - 1]:
                change += 1
            current_row[j] = min(add, delete, change)

    return current_row[n]


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query')
    page = int(request.args.get('page', 1))

    q = Article.query.search(query, sort=True)
    answers = q.paginate(page, 10, False).items
    counts = count_estimate(q, db.session)
    if counts < 20000:
        counts = get_count(q)
    else:
        counts = 10000 * (counts // 10000)

    npages = int(math.ceil(counts / 10))
    for answer in answers:
        if answer.title is not None:
            answer.title = answer.title[2:]
            answer.title = answer.title[:-1]
            if answer.title[0] == '[':
                answer.title = answer.title[1:]
                answer.title = str(answer.title[:-2]) + '.'
        else:
            answer.title = ''

        if answer.abstract is not None:
            answer.abstract = answer.abstract[2:]
            answer.abstract = answer.abstract[:-1]
        else:
            answer.abstract = ''
        if answer.pubdate is not None:
            answer.pubdate = answer.pubdate.strftime('Published at %d, %b %Y')
        else:
            answer.pubdate = ''

        answer.authorlist = []
        try:
            for author in json.loads(answer.authors)['Author']:
                answer.authorlist.append(author['LastName'] + ' ' + author['ForeName'])
        except:
            answer.authorlist.append('')

    return render_template('search.html', title=query, answers=answers, query=query, counts=counts, npages=npages,
                           page=page)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    if request.args.get('task') is not None:
        if request.args.get('task') == 'parse':
            job = q.enqueue_call(
                func=parse_them_all, args=(), result_ttl=50000, timeout=360000
            )
    print(job.get_id())
    return render_template('admin.html', title='admin')


@app.route('/update_journals', methods=['GET'])
def update_journals():
    # Token check
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    acs = []

    task = request.args.get('task')

    if task == 'parse':
        # ACS
        #   Some basic start in parsing
        parsing = False
        url = 'https://pubs.acs.org/loi/achre4'
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        journals = soup.find(id="journal-az-layer").find_all('a')
        print(url)

        # Journal-by-journal
        for journal in journals:
            url = journal['href']
            journal_name = journal.text
            print(journal_name)

            url = url.split('/')[2]
            url = 'https://pubs.acs.org/loi/' + url

            # Check for journal existence / add if not exist
            if Journal.query.filter_by(name=journal_name).first() is None:
                journal = Journal(name=journal_name, url=url, last_fetched=datetime.datetime.now(), last_issue='0',
                                  last_volume='0')
                db.session.add(journal)
                db.session.commit()

            # Start queue

            job = q.enqueue_call(
                func=parse_journal, args=(url, journal_name), result_ttl=50000, timeout=360000
            )

            #   Some cool thing for online monitoring (see in update.html)
            our_journal = Journal.query.filter_by(name=journal_name).first()
            our_journal.job_id = job.get_id()

            db.session.commit()

        return redirect(
            url_for('update_journals', token='64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0'))

    for journal in Journal.query.order_by(Journal.id).all():
        acs.append({'name': journal.name, 'job_id': journal.job_id})

    return render_template('update.html', title='Database update', acs=acs)


@app.route('/get_acs_abs', methods=['GET'])
def get_acs_abs():
    return render_template('get_acs_abs.html')


@app.route('/update_acs', methods=['GET'])
def update_abs():
    job = q.enqueue_call(
        func=parse_abstracts, args=(int(request.args.get('firstid')), int(request.args.get('lastid'))), result_ttl=50000,
        timeout=360000
    )

    job_id = job.get_id()

    return redirect(url_for('results_update_acs', job_id=job_id))

@app.route('/results_update_acs', methods=['GET'])
def results_update_acs():
    job_id = request.args.get('job_id')
    return render_template('acs_abs.html', job_id=job_id)


@app.route('/article', methods=['GET'])
def article():
    id = request.args.get('id')

    if id is None:
        return redirect(url_for('index'))

    query = request.args.get('query', '')

    article = Article.query.get_or_404(id)
    if article.title is not None:
        article.title = article.title[2:]
        article.title = article.title[:-1]
        if article.title[0] == '[':
            article.title = article.title[1:]
            article.title = str(article.title[:-2]) + '.'
    else:
        article.title = ''

    if article.abstract is not None:
        article.abstract = article.abstract[2:]
        article.abstract = article.abstract[:-1]
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

    return render_template('article.html', title=article.title, article=article, query=query)


@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):
    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        return "Success", 200
    else:
        if job.is_failed:
            return 'Failure', 403
        else:
            return "No", 202


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

    return render_template('login.html', login_url=(auth.get_login_url()))


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

    return render_template('library.html', name=name, docs=docs, title='Library')


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

    return render_template('account.html', name=name, email=email)


@app.route('/logout')
def logout():
    session.pop('token', None)
    return redirect('/')


def parse_them_all():
    parsing = False
    journal_inp = 'Analytical Chemistry'
    url = 'https://pubs.acs.org/loi/achre4'
    start_volume = 18
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    journals = soup.find(id="journal-az-layer").find_all('a')
    print(url)
    for journal in journals:
        url = journal['href']
        journal_name = journal.text
        print(journal_name)
        if (journal_name == journal_inp):
            parsing = True
            print('Success')
        if (parsing):
            url = url.split('/')[2]
            url = 'https://pubs.acs.org/loi/' + url
            parse_journal(url, journal_name=journal_name, start_volume=start_volume)
            start_volume = -1


def parse_journal(url, journal_name):
    journal = Journal.query.filter_by(name=journal_name).first()
    # Start parsing
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    volumes = soup.find_all("div", class_="slider")
    last_volume = volumes[0]['id'][6:]
    issues = volumes[0].find_all('div', class_='row')
    last_issue = (issues[0].a['href']).split('/')[-1]
    for volume in volumes:
        issues = volume.find_all('div', class_='row')
        for issue in issues:
            url_is = issue.a['href']
            if (int(volume['id'][6:]) > int(journal.last_volume)) or \
                    ((int(volume['id'][6:]) == int(journal.last_volume)) and (
                                int((issue.a['href']).split('/')[-1]) >= int(journal.last_issue))):
                parse_issue(url=url_is, volume=volume['id'][6:], journal_id=journal.id)
    journal.last_volume = last_volume
    journal.last_issue = last_issue
    db.session.commit()


def parse_issue(url, volume, journal_id):
    response = requests.get(url)
    issue = (url.split('/'))[-1]
    soup = BeautifulSoup(response.content, 'html.parser')
    print("Enter JN: " + str(journal_id) + " volume: " + str(volume) + " issue: " + str(issue))
    articles_db = Article.query.filter_by(journal_id=journal_id, volume=volume, issue=issue)
    months_dict = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8,
                   'September': 9, 'October': 10, 'November': 11, 'December': 12}
    article_groups = soup.find_all("div", class_="articleGroup")

    print("Parse JN: " + str(journal_id) + " volume: " + str(volume) + " issue: " + str(issue))
    for article_group in article_groups:
        try:
            article_group_name = article_group.find_all("div", class_="subject")[0].get_text("\n")
        except:
            article_group_name = "error"

        articles = article_group.find_all("div", class_="articleBox")

        for article in articles:
            title = ''
            try:
                title = str(article.find_all('div', class_='art_title linkable')[0].a.text.encode(encoding="UTF-8"))
            except:
                title = 'artica-technical:notitle'

            authors = []
            for author in article.find_all('span', class_='entryAuthor normal hlFld-ContribAuthor'):
                authors.append(author.text.replace('\n', '').replace('\r', ' '))

            try:
                page_range = article.find_all('span', class_='articlePageRange')[0].text
            except:
                page_range = 'artica-technical:nopage_range'

            try:
                pub_date = article.find_all('div', class_='epubdate')[0].text
                pub_date = pub_date.split(' ')

                if pub_date[2] == '(Web):':
                    month = pub_date[3]
                    month = int(months_dict[month])
                    day = int(pub_date[4][:-1])
                    year = int(pub_date[5])
                    pub_date = datetime.date(year=year, month=month, day=day)
                else:
                    month = pub_date[2]
                    month = int(months_dict[month])
                    day = int(pub_date[3][:-1])
                    year = int(pub_date[4])
                    pub_date = datetime.date(year=year, month=month, day=day)
            except:
                try:

                    pub_date = article.find_all('div', class_='epubdate')[0].text
                    pub_date = pub_date.split(' ')

                    if pub_date[2] == '(Web):':
                        month = pub_date[3]
                        month = int(months_dict[month])
                        day = 1
                        year = int(pub_date[4])
                        pub_date = datetime.date(year=year, month=month, day=day)
                    else:
                        month = pub_date[2]
                        month = int(months_dict[month])
                        day = 1
                        year = int(pub_date[3])
                        pub_date = datetime.date(year=year, month=month, day=day)
                except:
                    try:
                        pub_date = article.find_all('div', class_='coverdate')[0].text
                        pub_date = pub_date.split(' ')

                        if pub_date[2] == '(Web):':
                            month = pub_date[3]
                            month = int(months_dict[month])
                            day = int(pub_date[4][:-1])
                            year = int(pub_date[5])
                            pub_date = datetime.date(year=year, month=month, day=day)
                        else:
                            month = pub_date[2]
                            month = int(months_dict[month])
                            day = int(pub_date[3][:-1])
                            year = int(pub_date[4])
                            pub_date = datetime.date(year=year, month=month, day=day)
                    except:
                        pub_date = article.find_all('div', class_='coverdate')[0].text
                        pub_date = pub_date.split(' ')
                        if pub_date[2] == '(Web):':
                            month = pub_date[3]
                            month = int(months_dict[month])
                            day = 1
                            year = int(pub_date[4])
                            pub_date = datetime.date(year=year, month=month, day=day)
                        else:
                            month = pub_date[2]
                            month = int(months_dict[month])
                            day = 1
                            year = int(pub_date[3])
                            pub_date = datetime.date(year=year, month=month, day=day)

            print(pub_date)

            doi = ''
            try:
                doi = (article.find_all('div', class_='DOI')[0].text).replace('DOI: ', '')
            except:
                doi = 'artica-technical:nodoi'

            src = ''
            try:
                img = article.find_all('div', class_='articleFigure')[0].img
                if not (img['class'][0] == 'emptyImg'):
                    src = article.find_all('div', class_='articleFigure')[0].img['src']
                    src = 'https://pubs.acs.org/' + src
            except:
                src = 'artica-technical:nosrc'

            article = Article(title=title, pubdate=pub_date, volume=str(volume), issue=str(issue),
                              journal_id=journal_id, authors=authors, language='english',
                              doi=doi, doctype=article_group_name, source='acs site', src=src, pages=page_range,
                              technical_info=str(datetime.datetime.now()))
            db.session.add(article)
            db.session.commit()


def parse_abstracts(start_id=0, finish_id=0):
    articles = Article.query.filter(Article.id.between(start_id, finish_id)).order_by(Article.id).all()

    for article in articles:
        print(article.id)

        if article.meta_data is None:
            print('Not none')

            doi = article.doi
            if doi != '':
                url = 'http://pubs.acs.org/doi/' + doi

                k = True

                while k:
                    try:
                        response = requests.get(url)
                        k = False
                    except:
                        print('error')
                        time.sleep(1000)
                        k = True

                soup = BeautifulSoup(response.content, 'html.parser')

                meta_data = soup.find(id='articleMeta')

                if (meta_data is None):
                    meta_data = ''

                abstract_box = soup.find(id="abstractBox")
                abstract_body = soup.find(id="articleBody")

                if (abstract_box is not None):
                    try:
                        src = 'https://pubs.acs.org' + abstract_box.find(id="absImg").find_all('img')[0]['src']
                    except:
                        src = ''

                    abstract_parts = abstract_box.find_all("p", class_="articleBody_abstractText")

                    abstract = ''
                    try:
                        for abstract_part in abstract_parts:
                            abstract = abstract + abstract_part.text + ' '
                    except:
                        abstract = ''
                elif (abstract_body is not None):

                    src = ''

                    abstract_parts = abstract_body.find_all("p")

                    abstract = ''
                    try:
                        for abstract_part in abstract_parts:
                            abstract = abstract + abstract_part.text + ' '
                    except:
                        abstract = ''
                else:
                    abstract = ''
                    src = ''

                article.abstract = abstract
                article.src = src
                article.meta_data = str(meta_data)

                db.session.commit()
