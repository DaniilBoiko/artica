import requests, datetime, sys, random, threading, time
from bs4 import BeautifulSoup
from app.models import Article, Citation, Author, Journal, Affilation
from app import db
from app import app
import socket
import socks
import warnings
import os
from collections import defaultdict
from stem import Signal
from stem.control import Controller
from stem.connection import authenticate_none, authenticate_password

class TorInterface():
    controller = 'Not launched'
    password = "1234"

    def __init__(self):
        self.controller = Controller.from_port(port=9051)

    def connect(self):
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 9050, True)
        socket.socket = socks.socksocket
        print('Connection estabilished')

    def renew(self):
        self.controller.authenticate(self.password)
        self.controller.signal(Signal.NEWNYM)
        print ('New Tor circuit estabilished')

    def showMyIp(self):
        url = "http://www.showmyip.gr/"
        r = requests.Session()
        page = r.get(url)
        soup = BeautifulSoup(page.content, "html")
        ip_address = soup.find("span", {"class": "ip_address"}).text.strip()
        print(ip_address)

tor = TorInterface()

user_agent = 'Googlebot'
headers = {'User-Agent': user_agent}

'''
controller = Controller.from_port(port=9051)



socks.set_default_proxy(socks.SOCKS5, 'localhost', 9050)
socket.socket = socks.socksocket


def connectTor():
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5 , "localhost", 9050, True)
    socket.socket = socks.socksocket


def renew_tor():
    global controller
    global Password
    print ('Renewing Tor Circuit')
    if "stem.control.Controller" not in str(controller):
        # if global controller exist no more
        controller = Controller.from_port()
    # debug output
    print (controller)
    # authenticare the connection with the server control port
    controller.authenticate(Password)
    print ('Tor running version is : %s' % controller.get_version())
    # force a new circuit
    controller.signal(Signal.NEWNYM)
    # wait for new circuit
    time.sleep(10)
    print ('New Tor circuit estabilished')

def show_my_ip():
    url = "http://www.showmyip.gr/"
    r = requests.Session()
    page = r.get(url)
    soup = BeautifulSoup(page.content, "lxml")
    ip_address = soup.find("span",{"class":"ip_address"}).text.strip()
    print(ip_address)
'''

proxy_list = []
article_pool = []
journal_pool = []
ready_articles = 0
try_articles = 0
req_number = 0
'''
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
'''

def get_article(url):
    #n = True

    '''create_proxies()
    log(str(threading.current_thread())+'  '+str(proxies['https'])+'  proxies selected')'''

    global try_articles
    lock.acquire()
    try_articles += 1
    lock.release()

    '''while n:
        try:'''
    t = time.strftime('%X')
    response = requests.get('https://link.springer.com' + url, timeout=60)
    log(str(t)+' -- '+str(time.strftime('%X'))+'  '+str(threading.current_thread()) + '  ' + str(url)+ '  article requested')
    global req_number
    lock.acquire()
    req_number += 1
    lock.release()
    soup = BeautifulSoup(response.content, 'html.parser')

    article_title = soup.find('h1', class_='ArticleTitle').get_text()
    log(str(threading.current_thread())+'  '+str(url)+'  article_title parsed')
    doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[
          16:]
    log(str(threading.current_thread())+'  '+str(url)+'  doi parsed')
    # Проверяем наличие статьи в базе
    '''if doi is not None:
        article = Article.query.filter_by(doi=doi).first()
        if article is None:
            log(str(threading.current_thread()) + '  ' + str(url) + '  article not found in db')
            article = Article(doi=doi, title=article_title)
            log(str(threading.current_thread()) + '  ' + str(url) + '  article created')
            db.session.add(article)
            log(str(threading.current_thread()) + '  ' + str(url) + '  article added to db')
            db.session.commit()
            log(str(threading.current_thread()) + '  ' + str(url) + '  commit to db')

        else:
            log(str(threading.current_thread())+'  '+str(url)+'  article found in db')
            article.title = article_title
            log(str(threading.current_thread())+'  '+str(url)+'  article_title added to article')

    else:
        article = Article.query.filter_by(title=article_title).first()
        if article is None:
            article = Article(doi=doi, title=article_title)
            db.session.add(article)
            db.session.commit()
    # проверили
    log(str(threading.current_thread())+'  '+str(url)+'  article selected in db')
    
    if article.abstract is None:'''
    abstract = ''
    abstract_section = soup.find('section', class_='Abstract')
    if abstract_section is not None:
        for abstract_par in abstract_section.find_all('p'):
            abstract = abstract + abstract_par.get_text() + '\n'
        log(str(threading.current_thread()) + '  ' + str(url) + '  abstract parsed')
        '''if abstract == '':
            article.abstract = None
        else:
            article.abstract = abstract
        log(str(threading.current_thread()) + '  ' + str(url) + '  abstract added to article')
    '''
    ref = []
    ref_section = soup.find('section', class_='Section1 RenderAsSection1', id='Bib1')

    if ref_section is not None:
        for ref_item in ref_section.find_all('li', class_='Citation'):
            ref_doi = ref_item.find('span', class_='RefSource')
            if ref_doi is not None:
                if ref_doi.get_text()[:15] ==  'https://doi.org/':
                    ref.append(ref_doi.get_text()[16:])
                elif ref_doi.get_text()[:2] == '10.':
                    ref.append(ref_doi.get_text())

            else:
                ref_doi = ref_item.find('span', class_='Occurrence OccurrenceDOI')
                if ref_doi is not None:
                    ref.append(ref_doi.find('a', class_='gtm-reference')['href'][16:])

        log(str(threading.current_thread()) + '  ' + str(url) + '  references_doi parsed')
        '''
        for doi_item in ref:
            if Article.query.filter_by(doi=doi_item).first() is None:
                log(str(threading.current_thread()) + '  ' + str(doi_item) + '  article not found in db')
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
    log(str(threading.current_thread())+'  '+str(url)+'  references added to db, commit db')
        '''
    date = []
    date = soup.find('span', class_='article-dates__first-online')
    if date is not None:
        date_time = date.find('time')['datetime'].split('-')
        year = date_time.pop(0)
        month = date_time.pop(0)
        day = date_time.pop(0)
        '''date = datetime.date(year=int(year), month=int(month), day=int(day))
        article.pubdate = date
    log(str(threading.current_thread())+ ' date '+str(url))'''
    if soup.find('a', class_='ArticleCitation_Issue') is not None:
        volume = soup.find('span', class_='ArticleCitation_Volume').get_text().replace(',', '\t')[6:]
        issue = soup.find('a', class_='ArticleCitation_Issue').get_text().replace(',', '\t')[5:]
        pp = soup.find('span', class_='ArticleCitation_Pages').get_text().replace(',', '\t')[3:]
        '''article.volume = volume
        article.issue = issue
        article.pages = pp'''
    elif soup.find('span', class_='ArticleCitation_Volume') is not None:
        volume = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(0)
        issue = soup.find('time')['datetime'].split('-').pop(1).strip()
        if issue[0] == '0':
            issue = issue[1:]
        number = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(1)
        '''article.volume = volume
        article.issue = issue
        article.technical_info = number'''
    log(str(threading.current_thread()) + '  ' + str(url) + '  pubdate added to article')

    if soup.find('span', class_='bibliographic-information__value', id='electronic-issn') is not None:
        ISSN = soup.find('span', class_='bibliographic-information__value', id='electronic-issn').get_text()
    else:
        ISSN = soup.find('span', class_='bibliographic-information__value', id='print-issn').get_text()
    #article.issn = ISSN
    log(str(threading.current_thread())+'  '+str(url)+'  technical_info added to article')

    journal = soup.find('div', class_='enumeration')
    journal_url = journal.find_all('a')[0]
    log(str(threading.current_thread())+'  '+str((journal_url)['href']))
    #article.journal_id = Journal.query.filter_by(link='https://link.springer.com'+str(journal_url['href'])).first().id
    log(str(threading.current_thread())+'  '+str(url)+'  journal_id added to atrticle')

    key_section = soup.find('div', class_='KeywordGroup', lang="en")
    keywords = []
    if key_section is not None:
        for key_item in key_section.find_all('span', class_='Keyword'):
            keywords.append(key_item.get_text())
    #article.keyword = keywords
    log(str(threading.current_thread())+'  '+str(url)+'  keywords added to article')

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
            '''for aff in af_name:
                if Affilation.query.filter_by(aff=aff).first() is None:
                    new_aff = Affilation(aff=aff)
                    db.session.add(new_aff)
                    db.session.commit()'''

        # Check and add author
        for author_item in author_section.find_all('li', class_='u-mb-2 u-pt-4 u-pb-4'):
            author_name = author_item.find('span', class_='authors-affiliations__name')
            '''
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
    log(str(threading.current_thread())+' '+str(url)+'  authors and affiliations added, commit db')
            '''
    '''n = False

except (OSError, requests.exceptions.RequestException):
log('(!)' + str(threading.current_thread()) + '  ' + str(url) + '  Connection Error')
lock.acquire()
log(str(threading.current_thread()) + '  lock.acquire')
if proxy_item in proxy_list:
    proxy_list.remove(proxy_item)
log(str(threading.current_thread()) + '  proxies deleted')
lock.release()
log(str(threading.current_thread()) + '  lock.acquire')
create_proxies()
log(str(threading.current_thread()) + '  ' + str(proxies['https']) + '  proxies selected')'''

    global ready_articles
    lock.acquire()
    ready_articles += 1
    lock.release()


def get_article_pool(url):
    '''i = True
    create_proxies()
    log(str(threading.current_thread())+'  '+str(proxies['https'])+'  proxies selected')'''

    '''while i:
        try:'''
    t = time.strftime('%X')
    response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + str(url), timeout=60)
    log(str(t)+' -- '+str(time.strftime('%X'))+'  '+str(threading.current_thread())+'  '+str(url)+'  journal requested')
    global req_number
    lock.acquire()
    req_number += 1
    lock.release()
    soup = BeautifulSoup(response.content, 'html.parser')
    journal_title = soup.find('div', id='publication-title').find('h1').get_text()
    log(str(threading.current_thread())+'  '+str(url)+'  journal_title parsed')

    '''if Journal.query.filter_by(name=journal_title).first() is None:
        log(str(threading.current_thread())+'  '+str(url)+'  journal not found in db')
        new_journal = Journal(name=journal_title, link='https://link.springer.com/journal/' + url,
                              publisher='Springer')
        log(str(threading.current_thread())+'  '+str(url)+'  journal created')
        db.session.add(new_journal)
        log(str(threading.current_thread())+'  '+str(url)+'  journal added to db')
        db.session.commit()
        log(str(threading.current_thread())+'  '+str(url)+'  commit to db')

    journal = Journal.query.filter_by(name=journal_title).first()
    log(str(threading.current_thread())+'  '+str(url)+'  journal selected in db')'''
    issue_block = []
    volume_tab = soup.find('div', class_='volumes tab-content')
    for volume_item in volume_tab.find_all('div', class_='volume-item'):
        issue_list = volume_item.find('ul', class_='issues-list')
        for issue_item in issue_list.find_all('li', class_='issue-item'):
            issue_block.append(issue_item.find('a', class_='title')['href'])
            log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item.find('a', class_='title')['href'])+'  issue_link added to issue_pool')

    k = False
    for issue_item in issue_block:
        log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  issue_item selected in issue_pool')
        '''if journal.last_issue is not None:
            if issue_item == journal.last_issue:
                log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  last_issue found')
                k = True'''

        #if (journal.last_issue is None) or k:
        '''j = True
        while j:
            try:'''
        t = time.strftime('%X')
        response = requests.get('https://link.springer.com' + issue_item, timeout=60)
        log(str(t)+' -- '+str(time.strftime('%X'))+'  '+str(threading.current_thread()) + '  ' + str(url) + '  ' +str(issue_item)+ '  issue requested')
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find('div', class_='toc')
        for article_item in results.find_all('li'):
            article_link = article_item.find('h3', class_='title').find('a')['href']
            log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  '+str(article_link)+'  article_link parsed')
            #if Article.query.filter_by(doi=article_link[9:]).first() is None:
            #log(str(threading.current_thread())+'  '+str(article_link)+'  article not found in db')
            article_pool.append(article_link)
            log('(*)'+str(threading.current_thread())+'  '+str(article_link)+'  article_link added to article_pool')

            '''journal.last_issue = issue_item
            log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  '+'  last_issue determined')
            db.session.commit()
            log(str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  '+'  commit to db')'''
            #j = False

            k = True
            '''except (OSError, requests.exceptions.RequestException):
                log('(!)'+str(threading.current_thread())+'  '+str(url)+'  '+str(issue_item)+'  Connection Error')
                lock.acquire()
                log(str(threading.current_thread())+'  lock.acquire')
                if proxy_item in proxy_list:
                    proxy_list.remove(proxy_item)
                log(str(threading.current_thread())+'  proxies deleted')
                lock.release()
                log(str(threading.current_thread())+'  lock.acquire')
                create_proxies()
                log(str(threading.current_thread()) + '  ' + str(proxies['https']) + '  proxies selected')

        i = False

    except (OSError, requests.exceptions.RequestException):
        log('(!)' + str(threading.current_thread())+'  '+str(url)+'  Connection Error')
        lock.acquire()
        log(str(threading.current_thread()) + '  lock.acquire')
        if proxy_item in proxy_list:
            proxy_list.remove(proxy_item)
        log(str(threading.current_thread()) + '  proxies deleted')
        lock.release()
        log(str(threading.current_thread()) + '  lock.acquire')
        create_proxies()
        log(str(threading.current_thread()) + '  ' + str(proxies['https']) + '  proxies selected')'''


class Overwatch(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            print(time.strftime('%X'), ' |', '  threads: ', threading.active_count(), ' |',
                  '  article_pool: ', len(article_pool), ' |', '  ready: ', ready_articles, ' |', ' try: ', try_articles)

            time.sleep(10)

name = ''

class Helper(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def rin(self):
        with app.app.context():
            while True:
                global req_number
                if req_number > 100:
                    lock.acquire()
                    tor.renew()
                    lock.release()
                time.sleep(1)

class Worker(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
    def run(self):
        with app.app_context():
            while True:
                global article_pool
                while len(article_pool) != 0:
                    lock.acquire()
                    article_link = article_pool.pop()
                    lock.release()
                    log(str(threading.current_thread()) + ' in ' + str(article_link))
                    get_article(article_link)
                time.sleep(0.3)

class Miner(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
    def run(self):
        with app.app_context():
            while True:
                global journal_pool
                while len(journal_pool) != 0:
                    lock.acquire()
                    journal_link = journal_pool.pop()
                    lock.release()
                    log(str(threading.current_thread()) + ' in ' + str(journal_link))
                    get_article_pool(journal_link)
                time.sleep(0.3)

lock = threading.Lock()

def get_journal_pool(start, end):
    for item in range(int(start), int(end)):
        response = requests.get('https://link.springer.com/search/page/' + str(item) + '?facet-content-type="Journal"')
        log(str(item)+'  page requested')
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find('ol', class_='content-item-list')
        global journal_pool
        journal_pool = [result.find('a')['href'][9:] for result in results.find_all('li')]
        log(str(item)+'  journal_pool created')


def log(s):
    f = open('logs.txt', 'a')
    f.write(time.strftime('%X')+' '+s+'\n')
    f.close()


