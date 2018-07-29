import requests, datetime, sys, random, threading, time
from bs4 import BeautifulSoup
from app.models import Article, Citation, Author, Journal, Affilation
from app import db
from app import app

user_agent = 'Googlebot'
headers = {'User-Agent': user_agent}

ready_list = []
proxy_list = []
links = []
journal_pool = []
articles = 0
art = 0

def proxy_gen():
    global proxy_list
    proxy_req = requests.get('https://free-proxy-list.net', headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Cafari/537.36'}
                             )
    soup = BeautifulSoup(proxy_req.content, 'html.parser')
    proxies_table = soup.find(id='proxylisttable')
    for item in proxies_table.find('tbody').find_all('tr'):
        proxy_list.append({'ip': item.find_all('td')[0].get_text(), 'port': item.find_all('td')[1].get_text()})


def create_proxies():
    global proxies
    global proxy_item
    proxy_item = random.choice(proxy_list)
    proxies = {'https': 'http://' + proxy_item['ip'] + ':' + proxy_item['port']}


def get_article(url):
    n = True
    try:
        while n:
            create_proxies()
            try:
                log(str(threading.current_thread())+' start '+str(url))
                response = requests.get('https://link.springer.com' + url, proxies=proxies, timeout=60)
                log(str(threading.current_thread())+'  response article ' + str(url) + '  proxies: ' + proxies['https'])
                global art
                lock.acquire()
                art += 1
                lock.release()
                soup = BeautifulSoup(response.content, 'html.parser')

                article_title = soup.find('h1', class_='ArticleTitle').get_text()
                log(str(threading.current_thread())+' '+str(url))
                doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[
                      16:]
                log(str(threading.current_thread())+' '+str(doi))
                # Проверяем наличие статьи в базе
                if doi is not None:
                    article = Article.query.filter_by(doi=doi).first()
                    if article is None:
                        article = Article(doi=doi, title=article_title)
                        db.session.add(article)
                        db.session.commit()

                    else:
                        article.title = article_title
                else:
                    article = Article.query.filter_by(title=article_title).first()
                    if article is None:
                        article = Article(doi=doi, title=article_title)
                        db.session.add(article)
                        db.session.commit()
                log(str(threading.current_thread()) + ' check article ' + str(url))
                # проверили
                if article.abstract is not None:
                    abstract = ''
                    abstract_section = soup.find('section', class_='Abstract')
                    if abstract_section is not None:
                        for abstract_par in abstract_section.find_all('p'):
                            abstract = abstract + abstract_par.get_text() + '\n'
                    if abstract == '':
                        article.abstract = None
                    else:
                        article.abstract = abstract
                log(str(threading.current_thread())+' '+str(url)+' abstract')
                ref = []
                ref_section = soup.find('section', class_='Section1 RenderAsSection1', id='Bib1')

                if ref_section is not None:
                    for ref_item in ref_section.find_all('li', class_='Citation'):
                        ref_doi = ref_item.find('span', class_='RefSource')
                        if ref_doi is not None:
                            ref.append(ref_doi.get_text()[16:])
                        else:
                            ref_doi = ref_item.find('span', class_='Occurrence OccurrenceDOI')
                            if ref_doi is not None:
                                ref.append(ref_doi.find('a', class_='gtm-reference')['href'][16:])

                    for doi_item in ref:
                        if Article.query.filter_by(doi=doi_item).first() is None:
                            citing_article = Article(doi=doi_item)
                            db.session.add(citing_article)
                            db.session.commit()
                        cited_article = Article.query.filter_by(doi=doi_item).first()
                        if Citation.query.filter_by(cited=cited_article.id,
                                                    citing=article.id).first() is None:
                            citation = Citation(cited=cited_article.id,
                                                citing=article.id)
                            db.session.add(citation)
                            db.session.commit()
                log(str(threading.current_thread()) + ' ref '+str(url))
                date = []
                date = soup.find('span', class_='article-dates__first-online')
                if date is not None:
                    date_time = date.find('time')['datetime'].split('-')
                    year = date_time.pop(0)
                    month = date_time.pop(0)
                    day = date_time.pop(0)
                    date = datetime.date(year=int(year), month=int(month), day=int(day))
                    article.pubdate = date
                log(str(threading.current_thread())+ ' date '+str(url))
                if soup.find('a', class_='ArticleCitation_Issue') is not None:
                    volume = soup.find('span', class_='ArticleCitation_Volume').get_text().replace(',', '\t')[6:]
                    issue = soup.find('a', class_='ArticleCitation_Issue').get_text().replace(',', '\t')[5:]
                    pp = soup.find('span', class_='ArticleCitation_Pages').get_text().replace(',', '\t')[3:]
                    article.volume = volume
                    article.issue = issue
                    article.pages = pp
                elif soup.find('span', class_='ArticleCitation_Volume') is not None:
                    volume = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(0)
                    issue = soup.find('time')['datetime'].split('-').pop(1).strip()
                    if issue[0] == '0':
                        issue = issue[1:]
                    number = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(1)
                    article.volume = volume
                    article.issue = issue
                    article.technical_info = number

                ISSN = soup.find('span', class_='bibliographic-information__value', id='electronic-issn').get_text()
                article.issn = ISSN
                log(str(threading.current_thread())+' technical '+str(url))
                journal = soup.find('span', class_='JournalTitle').get_text()
                article.journal_id = Journal.query.filter_by(name=journal).first().id
                log(str(threading.current_thread()) + ' journal ' + str(url))
                key_section = soup.find('div', class_='KeywordGroup', lang="en")
                keywords = []
                if key_section is not None:
                    for key_item in key_section.find_all('span', class_='Keyword'):
                        keywords.append(key_item.get_text())
                article.keyword = keywords
                log(str(threading.current_thread()) + ' keywords ' + str(url))
                authors = []
                af = []
                emails = []
                af_name = []
                author_section = soup.find('div', class_='content authors-affiliations u-interface')
                if author_section is not None:
                    af_name_section = soup.find('ol', class_='test-affiliations')
                    if af_name_section is not None:
                        for af_name_item in af_name_section.find_all('li', class_='affiliation'):
                            af_name_dep = af_name_item.find('span', class_='affiliation__department')
                            if af_name_dep is not None:
                                af_dep = af_name_dep.get_text() + ', '
                            else:
                                af_dep = ''
                            af_name_name = af_name_item.find('span', class_='affiliation__name')
                            if af_name_name is not None:
                                af_n = af_name_name.get_text() + ', '
                            else:
                                af_n = ''
                            af_name_city = af_name_item.find('span', class_='affiliation__city')
                            if af_name_city is not None:
                                af_city = af_name_city.get_text() + ', '
                            else:
                                af_city = ''
                            af_name_country = af_name_item.find('span', class_='affiliation__country')
                            if af_name_country is not None:
                                af_country = af_name_country.get_text()
                            else:
                                af_country = ''
                            af_name.append(af_dep + af_n + af_city + af_country)
                        for aff in af_name:
                            if Affilation.query.filter_by(aff=aff).first() is None:
                                new_aff = Affilation(aff=aff)
                                db.session.add(new_aff)
                                db.session.commit()

                    # Check and add author
                    for author_item in author_section.find_all('li', class_='u-mb-2 u-pt-4 u-pb-4'):
                        author_name = author_item.find('span', class_='authors-affiliations__name')
                        if Author.query.filter_by(name=author_name.get_text()).first() is None:
                            new_author = Author(name=author_name.get_text())
                            db.session.add(new_author)
                            db.session.commit()
                        # Select author in db
                        author_db = Author.query.filter_by(name=author_name.get_text()).first()

                        af_section = author_item.find('ul', class_='authors-affiliations__indexes u-inline-list')
                        if af_section is not None:
                            for af_item in af_section.find_all('li'):
                                new_aff = Affilation(aff=af_name[int(af_item.get_text()) - 1])
                                db.session.add(new_aff)
                                db.session.commit()
                                author_db.affilations.append(
                                    new_aff)  # Добавляем aff для автора из списка aff_name по номеру aff
                                db.session.commit()

                        email_block = author_item.find('span', class_='author-information')
                        if email_block is not None:
                            email_name = email_block.find('a')['title']
                            if email_name is not None:
                                if Affilation.query.filter_by(aff=email_name).first() is None:
                                    new_aff = Affilation(aff=email_name)
                                    db.session.add(new_aff)
                                    db.session.commit()
                                new_aff = Affilation.query.filter_by(aff=email_name).first()
                                author_db.affilations.append(new_aff)
                                db.session.commit()
                                article.authors.append(author_db)
                                db.session.commit()
                db.session.commit()
                log(str(threading.current_thread()) + ' authors and affiliations ' + str(url))
                n = False

            except (OSError, requests.exceptions.RequestException):
                proxy_list.remove(proxy_item)

        global articles
        lock.acquire()
        articles += 1
        lock.release()

    except:
        log(str(url)+' Error')

def get_journal(url):
    i = True
    while i:
        create_proxies()
        try:
            response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + url, proxies=proxies, timeout=60)
            log('response journal '+url+'  proxies: '+proxies['https'])
            soup = BeautifulSoup(response.content, 'html.parser')
            journal_title = soup.find('div', id='publication-title').find('h1').get_text()
            log(url+' journal_title: '+journal_title)
            log('check '+journal_title)
            if Journal.query.filter_by(name=journal_title).first() is None:
                log(journal_title+' is not in the db')
                new_journal = Journal(name=journal_title, link='https://link.springer.com/journal/' + url,
                                      publisher='Springer')
                log('create '+journal_title)
                db.session.add(new_journal)
                log('add '+journal_title)
                db.session.commit()
                log(journal_title+': commit')

            journal = Journal.query.filter_by(name=journal_title).first()
            log('select '+journal_title)
            issue_block = []
            volume_tab = soup.find('div', class_='volumes tab-content')
            for volume_item in volume_tab.find_all('div', class_='volume-item'):
                issue_list = volume_item.find('ul', class_='issues-list')
                for issue_item in issue_list.find_all('li', class_='issue-item'):
                    issue_block.append(issue_item.find('a', class_='title')['href'])
                    log('add issue_link: '+issue_item.find('a', class_='title')['href'])

            k = False
            for issue_item in issue_block:
                log('issue_link: '+issue_item)
                log('check '+issue_item)
                if journal.last_issue is not None:
                    if issue_item == journal.last_issue:
                        log(issue_item+' is last_issue')
                        k = True

                if (journal.last_issue is None) or k:
                    j = True
                    while j:
                        create_proxies()
                        try:
                            response = requests.get('https://link.springer.com' + issue_item, proxies=proxies, timeout=60)
                            log(url+' response issue '+issue_item+'  proxies: '+proxies['https'])
                            soup = BeautifulSoup(response.content, 'html.parser')
                            results = soup.find('div', class_='toc')
                            for article_item in results.find_all('li'):
                                article_link = article_item.find('h3', class_='title').find('a')['href']
                                log('article_link: '+article_link)
                                if Article.query.filter_by(doi=article_link[9:]).first() is None:
                                    log(article_link+' is not in the db')
                                    links.append(article_link)
                                    log('{!} add '+article_link)

                            journal.last_issue = issue_item
                            db.session.commit()
                            log('issue '+issue_item+' commit')
                            j = False

                            k = True
                        except (OSError, requests.exceptions.RequestException):
                            log('Con_Error '+url+' '+issue_item)
                            proxy_list.remove(proxy_item)
                            log(proxies['https']+' delete')

            i = False

        except (OSError, requests.exceptions.RequestException):
            log('Con_Error ' +url)
            proxy_list.remove(proxy_item)
            log(proxies['https'] + ' delete')

class Overwatch(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            if len(proxy_list) < 50:
                proxy_gen()
            print(time.strftime('%X'),
                  '  proxies: ', len(proxy_list), '  threads: ', threading.active_count(),
                  '  links: ', len(links), '  ready articles: ', articles, ' try articles: ', art)
            time.sleep(10)


lock = threading.Lock()


def get_springer(start, end):

    for item in range(int(start), int(end)):
        response = requests.get('https://link.springer.com/search/page/' + str(item) + '?facet-content-type="Journal"')
        log('response page '+str(item))
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find('ol', class_='content-item-list')
        global journal_pool
        journal_pool = [result.find('a')['href'][9:] for result in results.find_all('li')]
        log(str(journal_pool))

        '''for result in results.find_all('li'):
            journal_link = result.find('a')['href'][9:]
            log('journal_link: '+journal_link)
            get_journal(journal_link)'''

        '''observer = Overwatch()
        observer.start()
        for it in range(10):
            name = 'Thread-' + str(it)
            t = threading.Thread(name=name, target=get_journal)
            t.start()
        
        observer.join()'''


def worker():
    with app.app_context():
        while True:
            while len(links) != 0:
                lock.acquire()
                link = links.pop()
                lock.release()
                get_article(link)
            time.sleep(0.3)

def mainer():
    with app.app_context():
        while True:
            global journal_pool
            while len(journal_pool) != 0:
                lock.acquire()
                journal_link = journal_pool.pop()
                lock.release()
                log(str(threading.current_thread())+' '+str(journal_link))
                get_journal(journal_link)
            time.sleep(0.3)

def log(s):
    f = open('logs.txt', 'a')
    f.write(time.strftime('%X')+' '+s+'\n')
    f.close()
