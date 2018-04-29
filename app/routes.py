from flask import render_template, request, redirect, url_for, jsonify, make_response
from app import app
from app import db
from app import q, Job, conn
from app.models import Article
import xmltodict, datetime, json,collections


def parseXMLs():
    for i in range(1, 11):
        print(i)
        with open('/data/ftp.ncbi.nlm.nih.gov/pubmed/baseline/pubmed18n{0}.xml'.format(str('{:04d}'.format(i)))) as fd:
            doc = xmltodict.parse(fd.read())
            for article in doc['PubmedArticleSet']['PubmedArticle']:
                try:
                    title = article['MedlineCitation']['Article']['ArticleTitle']
                except:
                    title = None

                try:
                    abstract = article['MedlineCitation']['Article']['Abstract']['AbstractText']
                    if type(abstract[0]) is collections.OrderedDict:
                        abstract = abstract['#text']
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

                article = Article(title=title, abstract=abstract, pubdate=pubdate, volume=volume, issue=issue,
                                  journal=journal, journalabbr=journalabbr, authors=authors, language=language,
                                  keyword=keywords, issn=issn)
                db.session.add(article)
                db.session.commit()
    return 'success'


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query')
    return render_template('search.html', title='Home', query=query)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    if request.args.get('task') is not None:
        if request.args.get('task') == 'parseXML':
            parseXMLs()

    return render_template('admin.html', title='admin')


@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):
    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        return "Yep!", 200
    else:
        return "Nay!", 202
