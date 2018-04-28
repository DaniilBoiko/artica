from flask import render_template, request, redirect, url_for, jsonify
from app import app
from app import db
from app import q, Job, conn

def parseXMLs():
    result = []
	def parseXML():
    for i in range(1, 2):
        with open('/data/ftp.ncbi.nlm.nih.gov/pubmed/baseline/pubmed18n{0}.xml'.format(str('{:04d}'.format(i)))) as fobj:
            doc = xmltodict.parse(fd.read())
            for article in doc['PubmedArticleSet']['PubmedArticle']:
                try:
                    title = article['MedlineCitation']['Article']['ArticleTitle']
                except KeyError:
                    title = None  
                ##########################################
                try:
                    abstract = article['MedlineCitation']['Article']['Abstract']['AbstractText']
                except KeyError:
                    abstract = None
                ##########################################
                try:
                    year = int(article['MedlineCitation']['DateCompleted']['Year'])
                    month = int(article['MedlineCitation']['DateCompleted']['Month'])
                    day = int(article['MedlineCitation']['DateCompleted']['Day'])
                    pubdate = datetime.date(year=year, month=month, day=day)
                except KeyError:
                    pubdate = None
                ##########################################
                try:
                    volume = int(article['MedlineCitation']['Article']['Journal']['JournalIssue']['Volume'])
                except KeyError:
                    volume = None
                ##########################################
                try:
                    issue = int(article['MedlineCitation']['Article']['Journal']['JournalIssue']['Issue'])
                except KeyError:
                    issue = None
                ##########################################
                try:
                    journal = article['MedlineCitation']['Article']['Journal']['Title']
                except KeyError:
                    journal = None
                ##########################################    
                try:
                    journalabbr = article['MedlineCitation']['Article']['Journal']['ISOAbbreviation']
                except KeyError:
                    journalabbr = None
                ##########################################    
                try:
                    authors = article['MedlineCitation']['Article']['Journal']['Title']
                except KeyError:
                    authors = None
                ##########################################
                try:
                    language = article['MedlineCitation']['Article']['Language']
                except KeyError:
                    language = None
                ##########################################
                try:
                    keywords = []
                    for topic in article['MedlineCitation']['MeshHeadingList']['MeshHeading']:
                        keywords.append(topic['DescriptorName']['#text'])
                except KeyError:
                    keywords = None
                ##########################################
                try:
                    issn = article['MedlineCitation']['Article']['Journal']['ISSN']['#text']
                except KeyError:
                    issn = None
    return result

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query')
    return render_template('search.html', title='Home',query=query)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    if request.args.get('task') is not None:
        if request.args.get('task') == 'parseXML':
            job = q.enqueue_call(
                func=parseXMLs, args=(), result_ttl=50000
            )
            print(job.get_id())

    return render_template('admin.html', title='admin')


@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):

    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        return str(job.result), 200
    else:
        return "Nay!", 202
