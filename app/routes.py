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
from sqlalchemy import func, between
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text
from sqlalchemy_searchable import search

from app import app
from app import db
from app import q, Job, conn, get_current_job
from app.models import Article, User, UserDocument, Journal, Citation, Author, Affilation

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
        user_agent = 'Googlebot'
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers)
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

    if task == 'wiley_get_journals':
        job = q.enqueue_call(
            func=get_wiley_journals, result_ttl=50000, timeout=360000
        )

        return redirect(
            url_for('update_journals', token='64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0',
                    w_j_task_number=job.get_id()))

    if task == 'wiley_update_journals':
        start = request.args.get('start')
        end = request.args.get('end')

        if (start is not None) and (end is not None):
            job = q.enqueue_call(
                func=parse_wiley_journals, args=(start, end), result_ttl=50000, timeout=360000
            )
            job_id = job.get_id()
            return redirect(
                url_for('update_journals', token='64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0',
                        wiley_job_id=job_id))
        else:
            return 'Describe all args', 404

    for journal in Journal.query.order_by(Journal.id).all():
        acs.append({'name': journal.name, 'job_id': journal.job_id})

    if request.args.get('wiley_job_id') is not None:
        wiley_job_id = request.args.get('wiley_job_id')
    else:
        wiley_job_id = 'No_job'

    return render_template('update.html', title='Database update', acs=acs, wiley_job_id=wiley_job_id)


@app.route('/get_acs_abs', methods=['GET'])
def get_acs_abs():
    return render_template('get_acs_abs.html')


@app.route('/update_acs', methods=['GET'])
def update_abs():
    job = q.enqueue_call(
        func=parse_abstracts, args=(int(request.args.get('firstid')), int(request.args.get('lastid'))),
        result_ttl=50000,
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


@app.route("/results_wiley/<job_key>", methods=['GET'])
def get_results_wiley(job_key):
    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        return "Success", 200
    else:
        if job.is_failed:
            return 'Failure', 403
        else:
            return jsonify(journal=job.meta.journal, volume=job.meta.volume, issue=job.meta.issue, start=job.meta.start,
                           end=job.meta.end, index = job.meta.index, year = job.meta.year), 202


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
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
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
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
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
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
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
                        user_agent = 'Googlebot'
                        headers = {'User-Agent': user_agent}
                        response = requests.get(url, headers=headers)
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


# ------------------------------------------------------------------------------
#                                   Wiley
# ------------------------------------------------------------------------------


def get_wiley_journals():
    # --------------
    # Wiley journals Проверил
    # --------------

    url = 'https://onlinelibrary.wiley.com/action/showPublications?PubType=journal&startPage='
    k = True
    i = 0
    journal_list = []
    while k:
        url_page = url + str(i)
        user_agent = 'Googlebot'
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        no_results = soup.find("li", class_='search-result__no-result')
        if no_results is not None:
            k = False
        else:
            journals = soup.find_all("li", class_='clearfix separator search__item')
            for journal in journals:
                title = journal.find(class_='meta__title meta__title__margin')
                link = title.a['href']
                journal_info = [title.text, link]
                journal_list.append(journal_info)
                new_journal = Journal(name=title.text, link=link, publisher='Wiley')
                db.session.add(new_journal)
                db.session.commit()
            i += 1


def parse_wiley_journals(start, end):
    # -------------------------
    # Parse journal by journal
    # -------------------------

    job = get_current_job()

    journals = Journal.query.filter_by(publisher='Wiley').all()
    job.meta.start = start
    job.meta.end = end
    i = 0

    for journal in journals:

        if i >= start or i <= end:

            job.meta.index = i
            job.meta.journal = Journal.name

            url = 'https://onlinelibrary.wiley.com/loi/' + journal.link.split('/')[2]
            user_agent = 'Googlebot'
            headers = {'User-Agent': user_agent}
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            loi_list = soup.find('ul', class_='rlist loi__list')

            if loi_list is not None:
                loi_list = loi_list.find_all('li')
                for li in loi_list:
                    if li.has_attr('class') and li['class'][0] != ' active ':
                        li_nested = li.find('ul')
                        if li_nested is None:
                            get_wiley_year(li.find('a')['href'])
                    else:
                        get_wiley_year(li.find('a')['href'], job)

            journal.last_fetched = datetime.datetime.now()

        i += 1


def get_wiley_year(url, job):
    # ----------------------------------
    # Gets an URL of Wiley journal year
    # ----------------------------------
    job.meta.year = url.split('/')[4]
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get('https://onlinelibrary.wiley.com' + url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    issues = soup.find_all(class_="rlist loi__issues")
    if issues is not None:
        for issue_item in issues:
            print(issue_item.text)
            issue_list = issue_item.find_all('li', class_="card clearfix")
            for issue in issue_list:
                link = issue.find(class_='parent-item').find('a')
                get_wiley_volume(link['href'], job)


def get_wiley_volume(url, job):
    # ------------------------------------
    # Gets an URL of Wiley journal volume
    # ------------------------------------

    job.meta.volume = url.split('/')[4]
    job.meta.issue = url.split('/')[5]
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get('https://onlinelibrary.wiley.com' + url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    articles = soup.find_all('div', class_='issue-item')

    for article in articles:
        get_wiley_article('https://onlinelibrary.wiley.com' + article.find('a', class_='issue-item__title')['href'])


def get_wiley_article(url):
    # -------------------------------------
    # Gets an URL of Wiley journal article
    # -------------------------------------

    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')


    doi = soup.find('a', class_='epub-doi')
    if doi is not None:
        doi = doi.text[16:]
        new_article = Article.query.filter_by(doi=doi).first()
        if new_article is None:
            new_article = Article()
            new_article.doi = doi
            db.session.add(new_article)
            db.session.commit()

    else:
        new_article = Article()
        db.session.add(new_article)
        db.session.commit()


    journal_name = soup.find('a', class_='citation--logo')['title'][0:-9]
    journal = Journal.query.filter_by(name=journal_name).first()
    article.journal_id = journal.id

    # Aricle main data

    title = wiley_to_text(soup.find('h2', class_='citation__title'))
    new_article.title = title

    abstract = wiley_to_text(soup.find('div', class_='article-section__content en main'))
    new_article.abstract = abstract

    author_group = soup.find('div', class_='loa-wrapper loa-authors hidden-xs')
    if author_group is not None:
        authors = author_group.find_all('div', class_='accordion-tabbed__tab-mobile accordion__closed')
        for author in authors:

            name = author.find('a', class_='author-name accordion-tabbed__control').text
            if not check_author(name):
                new_author = Author(name=name)
                db.session.add(new_author)
                db.session.commit()

            author_db = Author.query.filter_by(name=name).first()

            affilation_el = author.find('div', class_='author-info accordion-tabbed__content').find_all('p')
            for affilation in affilation_el:
                if not check_affilation(affilation.text):
                    new_affilation = Affilation(aff=affilation.text)
                    db.session.add(new_affilation)
                    db.session.commit()

                get_affilation = Affilation.query.filter_by(aff=affilation.text).first()
                author_db.affilations.append(get_affilation)

            db.session.commit(author_db)
            new_article.authors.append(author_db)

    doctype = wiley_to_text(soup.find('span', class_='primary-heading'))
    new_article.doctype = doctype

    date = soup.find('span', class_='epub-date')
    if date is not None:
        months_dict = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8,
                       'September': 9, 'October': 10, 'November': 11, 'December': 12}

        date = date.text.split()
        day = int(date[0])
        month = date[1]
        month = int(months_dict[month])
        year = int(date[2])
        date = datetime.date(year=year, month=month, day=day)
    new_article.pubdate=date

    cited_by = wiley_to_text(soup.find('div', class_='epub-section cited-by-count'))
    if cited_by is not None: cited_by = cited_by.split()[2]
    new_article.citation_counts=cited_by

    src = soup.find('img', class_='figure__image')
    if src is not None:
        src = src['src']
    new_article.src=src

    volume_issue = soup.find('p', class_='volume-issue')
    if volume_issue is not None:
        volume_issue = volume_issue.find_all('span', class_='val')
        volume = volume_issue[0].text
        issue = volume_issue[1].text
        new_article.volume=volume
        new_article.issue=issue

    pages = soup.find('p', class_='page-range')
    if pages is not None:
        pages = pages.find_all('span')[1].text
    new_article.pages=pages

    # Cited by

    cited_by_list = soup.find_all('li', class_='citedByEntry')
    for cited_by_item in cited_by_list:
        if cited_by_item.find('div', class_='extra-links') is not None:
            citation_doi =  cited_by_item.find('div', class_='extra-links').find('a')['href'][16:]
            if Article.query.filter_by(doi=doi) is not None:
                citing_article = Article(doi=doi)
                db.session.add(citing_article)
                db.session.commit()
            citing_article = Article.query.filter_by(doi=doi)
            new_citation = Citation(cited=new_article,
                                citing=citing_article)
            db.session.add(new_citation)
            db.session.commit()

    keyword_list = []
    keywords = soup.find('section', class_='keywords')
    if keywords is not None:
        keywords = keywords.find_all('li')
        for keyword in keywords:
            keyword_list.append(keyword.text)
    new_article.keyword = keyword_list

    db.session.commit()


# ------------------------------------------------------------------------------
#                           Common parsing functions
# ------------------------------------------------------------------------------

def check_author(name):
    author = Author.query.filter(name=name).first()
    if author is None:
        return False
    else:
        return True


def check_affilation(aff):
    author = Affilation.query.filter(aff=aff).first()
    if author is None:
        return False
    else:
        return True


def wiley_to_text(element):
    if element is not None:
        return element.text
    else:
        return None


# ------------------------------------------------------------------------------
#                           Elsevier
# ------------------------------------------------------------------------------

def parse_elsevier():
    for i in range(1, 149):
        url = ('https://www.elsevier.com/catalog?page=%d&producttype=journals&series=&sort=datedesc' % i)
        user_agent = 'Googlebot'
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        journals = soup.find_all("div", class_="row listing-products ")

        for journal in journals:
            title_for_parse = journal.find('a')['href'].split('/')[-1]
            title = elsevier_to_text(journal.find('a'))
            link = 'https://www.sciencedirect.com/journal/' + title_for_parse + '/vol/1/issue/1'
            journal = Journal.query.filter_by(name=title).first()
            if journal is None:
                new_journal = Journal(name=title, link=link)
                db.session.add(new_journal)
                db.session.commit()
            journal = Journal.query.filter_by(name=title).first()
            print(title)
            parse_elsevier_journal(url=link, journal_id=journal.id)


def parse_elsevier_journal(url, journal_id):
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    article_lists = soup.find("ol", class_="js-jl-aip-list article-list-items")

    article_lis = []

    if (article_lists is not None):
        article_list_ols = article_lists.find_all('ol', class_='article-list')
        if (len(article_list_ols) > 0):
            for article_list_ol in article_list_ols:
                article_lis = article_lis + article_list_ol.find_all('li')
        else:
            article_lis = article_lists.find_all('li')

    vol_issue = elsevier_to_text(soup.find('h2', class_='u-text-light u-h1 js-vol-issue'))

    vol_issue = vol_issue.split(' ')

    volume = ''
    issue = ''

    if (len(vol_issue) == 4):
        volume = vol_issue[1][:-1]
        issue = vol_issue[3]
    elif (len(vol_issue) == 2):
        volume = vol_issue[1]
        issue = 'without'

    for article_li in article_lis:
        article = article_li.find('a')
        parse_elsevier_article('https://www.sciencedirect.com' + article['href'], volume=volume, issue=issue,
                               journal_id=journal_id)

    next_page = soup.find('div', class_='els-jl-issue-navigate u-padding-hor-xs issue-navigation')

    if (next_page is not None):
        next_page = next_page.find_all('a')
    else:
        next_page = ''

    if next_page != '':
        if (next_page[1]['aria-disabled'] == 'false'):
            print('next_page')
            next_page = 'https://www.sciencedirect.com' + next_page[1]['href']
            parse_elsevier_journal(next_page, journal_id=journal_id)


def parse_elsevier_article(url, volume, issue, journal_id):
    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    keyword_div = soup.find('div', class_='Keywords')
    keywords = []
    if (keyword_div is not None):
        kw_divs = keyword_div.find_all('div', class_='keywords')
        for kw_div in kw_divs:
            span = kw_div.find('span')
            if span is not None:
                keywords.append(span.text)



    title = elsevier_to_text(soup.find('span', class_='title-text'))
    doi = '/'.join(elsevier_to_text(soup.find('a', class_='doi')).split('/')[-2:])

    p_abs = soup.find('div', class_='abstract author')
    if (p_abs is not None):
        p_abs = p_abs.find_all('p')
    else:
        p_abs = ''

    abstract = ''

    for p_ab in p_abs:
        abstract = str(p_ab.text) + ' '

    abstract = abstract[:-1]

    a_authors = soup.find('div', class_='author-group')
    if (a_authors is not None):
        a_authors = a_authors.find_all('a', class_='author size-m workspace-trigger')
    else:
        a_authors = ''

    authors = []

    for a_author in a_authors:
        first_name = elsevier_to_text(a_author.find('span', class_='text given-name'))
        second_name = elsevier_to_text(a_author.find('span', class_='text surname'))
        affs = a_author.find_all('span', class_='author-ref')
        affiliation = []
        for aff in affs:
            affiliation.append(aff.text)
        authors.append({'Name': first_name + ' ' + second_name, 'Aff_labels': affiliation})

    a = elsevier_to_text(soup.find('script', type='application/json'))

    affiliations = {}

    if a != '':
        json_data = json.loads(a)

        js_affiliations = json_data['authors']['affiliations']

        for key in js_affiliations:
            try:
                label = js_affiliations[key]['$$'][0]['_']
                text = js_affiliations[key]['$$'][1]['_']
                affiliations[label] = text
            except:
                pass


    for label in affiliations:
        if not check_affilation(affiliations[label]):
            new_affilation = Affilation(aff=affiliations[label])
            db.session.add(new_affilation)
            db.session.commit()

        get_affilation = Affilation.query.filter_by(aff=affiliations[label]).first()
        affiliations['label'] = get_affilation

    authors_with_aff = []

    for author in authors:
        author_affiliation = []
        for label in author['Aff_labels']:
            if (label in affiliations):
                author_affiliation.append(affiliations[label])
        authors_with_aff.append([author['Name'], author_affiliation])

    author_to_db = []

    for author in authors_with_aff:
        if not check_author(author[0]):
            new_author = Author(name=author[0])
            for affiliation in author[1]:
                new_author.affilations.append(affiliation)
            db.session.add(new_author)
            db.session.commit()

            author_to_db.append(Author.query.filter_by(name=author[0]).first().id)

    vol = elsevier_to_text(soup.find('a', title='Go to table of contents for this volume/issue')) + ', '

    vol_date_page = soup.find('div', class_='publication-volume u-text-center')

    if (vol_date_page is not None):
        vol_date_page = elsevier_to_text(vol_date_page.find('div', class_='text-xs'))
    else:
        vol_date_page = ''

    data_page = vol_date_page.replace(vol, '')

    months_dict = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8,
                   'September': 9, 'October': 10, 'November': 11, 'December': 12}

    words = data_page.split(' ')
    try:
        if (words[2] == 'Pages'):
            pages = words[3]
            day = 1
            month = words[0]
            month = int(months_dict[month])
            year = int(words[1][:-1])
            pub_date = datetime.date(year=year, month=month, day=day)
        else:
            pages = words[4]
            day = int(words[0])
            month = words[1]
            month = int(months_dict[month])
            year = int(words[2][:-1])
            pub_date = datetime.date(year=year, month=month, day=day)
    except:
        pages = ''
        pub_date = ''

    new_url = 'https://www.sciencedirect.com/sdfe/arp/pii/' + url.split('/')[-1] + '/citingArticles'

    user_agent = 'Googlebot'
    headers = {'User-Agent': user_agent}
    new_response = requests.get(new_url, headers=headers)
    new_soup = elsevier_to_text(BeautifulSoup(new_response.content, 'html.parser'))
    citing_doi = []
    if (new_soup != ''):
        json_citing = json.loads(new_soup)
        for article in json_citing['articles']:
            citing_doi.append(article['doi'])

    citing_count = len(citing_doi)

    new_url = 'https://www.sciencedirect.com/sdfe/arp/pii/' + url.split('/')[-1] + '/references/external-links/3000'
    new_response = requests.get(new_url, headers=headers)
    new_soup = elsevier_to_text(BeautifulSoup(new_response.content, 'html.parser'))
    reference_doi = []
    if (new_soup != ''):
        json_citing = json.loads(new_soup)
        for article in json_citing:
            if 'crossRefDoi' in article:
                reference_doi.append(article['crossRefDoi'])


    new_article = Article(title=title, abstract=abstract, journal_id=journal_id, doi=doi,
                          source='elsevier', citation_counts=citing_count, volume=volume, issue=issue,
                          pubdate=pub_date, pages=pages, keyword = keywords)

    for author_to_db_element in author_to_db:
        new_article.authors.append(author_to_db_element)
    db.session.add(new_article)
    db.session.commit()

    #References

    for doi in reference_doi:
        if Article.query.filter_by(doi=doi) is not None:
            reference_article = Article(doi=doi)
            db.session.add(reference_article)
            db.session.commit()
        reference_article = Article.query.filter_by(doi=doi)
        new_citation = Citation(cited=reference_article,
                                citing=new_article)
        db.session.add(new_citation)
        db.session.commit()

    # Cited by
    for doi in citing_doi:
        if Article.query.filter_by(doi=doi) is not None:
            citing_article = Article(doi=doi)
            db.session.add(citing_article)
            db.session.commit()
        citing_article = Article.query.filter_by(doi=doi)
        new_citation = Citation(cited=new_article,
                                citing=citing_article)
        db.session.add(new_citation)
        db.session.commit()


def elsevier_to_text(obj):
    if obj is not None:
        return obj.text
    else:
        return ''
