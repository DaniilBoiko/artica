import math, requests, datetime, sys, random, threading, time, json, codecs
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
import multiprocessing as mp
import ctypes as ct
from translitcodec import translitcodec


def log(s):
    f = open('logs.txt', 'a')
    f.write(time.strftime('%X') + ' ' + s + '\n')
    f.close()


class TorInterface():
    controller = 'Not launched'
    password = "1234"

    def __init__(self):
        self.controller = Controller.from_port(port=9051)

    def connectTor(self):
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 9050, True)
        socket.socket = socks.socksocket
        print('Connection estabilished')

    def renewTor(self):
        self.controller.authenticate(self.password)
        self.controller.signal(Signal.NEWNYM)

    def showMyIp(self):
        url = "http://www.showmyip.gr/"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        ip_address = soup.find("span", {"class": "ip_address"}).text.strip()
        print ('New Tor circuit estabilished. IP: ', ip_address)


tor = TorInterface()

lock = threading.Lock()

user_agent = 'Googlebot'
headers = {'User-Agent': user_agent}

feeds = []


class SpringerParser():

    def __init__(self, miner_count, worker_count):
        self.name = 'SpringerParser'
        self.first = 0
        self.last = 0
        self.try_articles = 0
        self.ready_articles = 0
        self.article_pool = []
        self.journal_pool = []
        self.source_count = 0
        self.miner_count = miner_count
        self.worker_count = worker_count
        self.times = []
        log('Parser created')

    def create_watcher(self):
        watcher = Overwatch()
        watcher.start()
        log('watcher created')

    def create_commander(self):
        commander = TorCommander()
        commander.start()
        log('commander created')

    def create_sources(self):
        for i in range(int(self.first), int(self.last)):
            source = Source(name='Source-' + str(i), number=i)
            source.start()
            lock.acquire()
            self.source_count += 1
            lock.release()
            log('Source-' + str(i) + ' created')
            time.sleep(0.3)

    def create_miners(self):
        for i in range(self.miner_count):
            miner = Miner(name='Miner-' + str(i + 1))
            miner.start()
            log('Miner-' + str(i + 1) + ' screated')
            time.sleep(0.3)

    def create_workers(self):
        for i in range(self.worker_count):
            worker = Worker(name='Worker-' + str(i + 1))
            worker.start()
            log('Worker-' + str(i + 1) + ' created')
            time.sleep(0.3)


springer_parser = SpringerParser(miner_count=2, worker_count=20)


class Overwatch(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'Overwatch'
        self.zero = len(springer_parser.journal_pool)

    def run(self):
        while True:
            min_rtime = 'None'
            max_rtime = 'None'
            if springer_parser.times:
                min_rtime = str(min(springer_parser.times))
                max_rtime = str(max(springer_parser.times))
            print('th',
                  threading.active_count(), '|', 'pool:', len(springer_parser.article_pool), '|', 'jrls:',
                  len(springer_parser.journal_pool), '|', 'ready:', str(springer_parser.ready_articles))
            springer_parser.times = []
            time.sleep(1)


class TorCommander(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'TorCommander'

    def run(self):
        while True:
            time.sleep(60)
            lock.acquire()
            tor.renewTor()
            lock.release()


class Source(threading.Thread):

    def __init__(self, name, number):
        threading.Thread.__init__(self)
        self.name = name
        self.number = number

    def thread_name(self):
        label = str(str(threading.current_thread()).split(',')[0])
        return str(label.split('(')[1])

    def run(self):
        t = int(time.time())
        page_link = 'https://link.springer.com/search/page/' + str(self.number) + '?facet-content-type="Journal"'
        rtime = int(time.time()) - t
        response = requests.get(page_link)
        springer_parser.times.append(rtime)
        log(self.thread_name() + str(rtime) + ' page requested')
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find('ol', class_='content-item-list')
        lock.acquire()
        springer_parser.journal_pool += [result.find('a')['href'][9:] for result in results.find_all('li')]
        springer_parser.source_count -= 1
        lock.release()
        log(self.thread_name() + ' off')


class Miner(threading.Thread):

    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.url = ''

    def thread_name(self):
        label = str(str(threading.current_thread()).split(',')[0])
        return str(label.split('(')[1])

    def get_article_pool(self):
        year = ['2017', '2018']
        try:
            t = int(time.time())
            response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + str(self.url), timeout=60)
            rtime = int(time.time()) - t
            springer_parser.times.append(rtime)
            log(self.thread_name() + ' ' + str(rtime) + ' ' + str(self.url) + ' journal requested')

            soup = BeautifulSoup(response.content, 'html.parser')

            '''journal_title = soup.find('div', id='publication-title').find('h1').get_text()
            log(thread_name() + ' ' + str(url) + ' journal_title parsed')
    
            if Journal.query.filter_by(name=journal_title).first() is None:
                log(thread_name() + ' ' + str(url) + ' journal not found in db')
                new_journal = Journal(name=journal_title, link='https://link.springer.com/journal/' + url,
                                      publisher='Springer')
                log(thread_name() + ' ' + str(url) + ' journal created')
                db.session.add(new_journal)
                log(thread_name() + ' ' + str(url) + ' journal added to db')
                db.session.commit()
                log(thread_name() + ' ' + str(url) + ' commit to db')
    
            journal = Journal.query.filter_by(name=journal_title).first()
            log(thread_name() + ' ' + str(url) + ' journal selected in db')'''

            issue_block = []
            volume_tab = soup.find('div', class_='volumes tab-content')
            for volume_item in volume_tab.find_all('div', class_='volume-item'):
                issue_list = volume_item.find('ul', class_='issues-list')
                for issue_item in issue_list.find_all('li', class_='issue-item'):
                    issue_date = issue_item.find('a', class_='title').get_text().split(',')[0]
                    issue_year = str(issue_date.split(' ')[-1])
                    if issue_year in year:
                        issue_block.append(issue_item.find('a', class_='title')['href'])
                        log(self.thread_name() + ' ' + str(self.url) + ' ' + str(
                            issue_item.find('a', class_='title')['href']) + ' issue_link added to issue_pool')

            # k = False
            for issue_item in issue_block:
                '''log(thread_name() + ' ' + str(url) + ' ' + str(
                    issue_item) + ' issue_item selected in issue_pool')
                if journal.last_issue is not None:
                    if issue_item == journal.last_issue:
                        log(thread_name() + ' ' + str(url) + ' ' + str(issue_item) + ' last_issue found')
                        k = True'''

                # if (journal.last_issue is None) or k:
                t = int(time.time())
                response = requests.get('https://link.springer.com' + issue_item, timeout=60)
                rtime = int(time.time()) - t
                springer_parser.times.append(rtime)
                log(self.thread_name() + ' ' + str(rtime) + ' ' + str(self.url) + ' ' + str(issue_item) + ' issue requested')

                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find('div', class_='toc')
                for article_item in results.find_all('li'):
                    article_link = article_item.find('h3', class_='title').find('a')['href']
                    log(self.thread_name() + ' ' + str(self.url) + ' ' + str(issue_item) + ' ' + str(
                        article_link) + ' article_link parsed')
                    # if Search(Article, 'doi', article_link[9:]) is None:
                    # if Article.query.filter_by(doi=article_link[9:]).first() is None:
                    while len(springer_parser.article_pool) > 500:
                        time.sleep(20)
                    springer_parser.article_pool.append(article_link)
                    log(self.thread_name() + ' ' + str(
                        article_link) + ' article_link added to article_pool')

                # issue pages counter
                art_number = results.find('h2').find('span').get_text().split(' ')[0][1:]
                pages = int(art_number) // 20
                for item in range(0, pages):
                    issue_link = ''
                    for i in range(1, (len(issue_item.split('/')) - 1)):
                        issue_link += ('/' + str(issue_item.split('/')[i]))
                    issue_link += ('/' + str(int(issue_item.split('/')[(len(issue_item.split('/')) - 1)]) + item))
                    issue_item = issue_link
                    t = int(time.time())
                    response = requests.get('https://link.springer.com' + issue_item, timeout=60)
                    rtime = int(time.time()) - t
                    springer_parser.times.append(rtime)
                    log(str(threading.current_thread())+ ' ' + str(rtime) + ' ' + str(self.url) + ' ' + str(issue_item) + ' issue requested')

                    soup = BeautifulSoup(response.content, 'html.parser')
                    results = soup.find('div', class_='toc')
                    for article_item in results.find_all('li'):
                        article_link = article_item.find('h3', class_='title').find('a')['href']
                        log(self.thread_name() + ' ' + str(self.url) + ' ' + str(issue_item) + ' ' + str(
                            article_link) + ' article_link parsed')
                        while len(springer_parser.article_pool) > 500:
                            time.sleep(20)
                        springer_parser.article_pool.append(article_link)

                        # if Search(Article, 'doi', article_link[9:]) is None:
                        # if Article.query.filter_by(doi=article_link[9:]).first() is None:
                        # log(self.thread_name() + ' ' + str(
                        #    article_link) + ' article not found in db')
                        log(self.thread_name() + ' ' + str(
                            article_link) + ' article_link added to article_pool')
                # k = True

        except Exception as e:
            log('ERROR: ' + self.thread_name() + ' ' + str(self.url) + ' ' + str(e))

    def run(self):
        with app.app_context():
            while True:
                if springer_parser.journal_pool:
                    lock.acquire()
                    self.url = springer_parser.journal_pool.pop()
                    lock.release()
                    log(self.thread_name() + ' in ' + str(self.url))
                    self.get_article_pool()
                time.sleep(0.3)


class Worker(threading.Thread):

    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.url = ''

    def thread_name(self):
        label = str(str(threading.current_thread()).split(',')[0])
        return str(label.split('(')[1])

    def get_article(self):
        try:
            t = int(time.time())
            response = requests.get('https://link.springer.com' + self.url, timeout=60)
            rtime = int(time.time()) - t
            springer_parser.times.append(rtime)
            log(self.thread_name() + ' ' + str(rtime) + ' ' + str(
                self.url) + ' article requested')

            soup = BeautifulSoup(response.content, 'html.parser')

            article_title = soup.find('h1', class_='ArticleTitle').get_text()
            log(self.thread_name() + ' ' + str(self.url) + ' article_title parsed')

            doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[
                  16:]
            log(self.thread_name() + ' ' + str(self.url) + ' doi parsed')

            # Search article in database
            '''if doi is not None:
                article = Article.query.filter_by(doi=doi).first()
                if article is None:
                    log(thread_name() + ' ' + str(url) + ' article not found in db')
                    article = Article(doi=doi, title=article_title)
                    log(thread_name() + ' ' + str(url) + ' article created')
                    db.session.add(article)
                    log(thread_name() + ' ' + str(url) + ' article added to db')
                    db.session.commit()
                    log(thread_name() + ' ' + str(url) + ' commit to db')

                else:
                    log(thread_name() + ' ' + str(url) + ' article found in db')
                    article.title = article_title
                    log(thread_name() + ' ' + str(url) + ' article_title added to article')

            else:
                article = Article.query.filter_by(title=article_title).first()
                if article is None:
                    article = Article(doi=doi, title=article_title)
                    db.session.add(article)
                    db.session.commit()
            # Checked
            log(thread_name() + ' ' + str(url) + ' article selected in db')'''

            # if article.abstract is None:
            abstract = ''
            abstract_section = soup.find('section', class_='Abstract')
            if abstract_section is not None:
                for abstract_par in abstract_section.find_all('p'):
                    abstract = abstract + abstract_par.get_text() + '\n'
                log(self.thread_name() + ' ' + str(self.url) + ' abstract parsed')
                '''if abstract == '':
                    article.abstract = None
                else:
                    article.abstract = abstract
                log(thread_name() + ' ' + str(url) + ' abstract added to article')'''

            cited = []
            ref_section = soup.find('section', class_='Section1 RenderAsSection1', id='Bib1')
            if ref_section is not None:
                for ref_item in ref_section.find_all('li', class_='Citation'):
                    ref_doi = ref_item.find('span', class_='RefSource')
                    if ref_doi is not None:
                        if ref_doi.get_text()[:15] == 'https://doi.org/':
                            cited.append(codecs.encode(ref_doi.get_text()[16:], 'translit/one'))
                        elif ref_doi.get_text()[:2] == '10.':
                            cited.append(codecs.encode(ref_doi.get_text(), 'translit/one'))
                    else:
                        ref_doi = ref_item.find('span', class_='Occurrence OccurrenceDOI')
                        if ref_doi is not None:
                            cited.append(codecs.encode(ref_doi.find('a', class_='gtm-reference')['href'][16:], 'translit/one'))
                log(self.thread_name() + ' ' + str(self.url) + ' references_doi parsed')
                '''for doi_item in ref:
                    if Article.query.filter_by(doi=doi_item).first() is None
                        log(thread_name() + ' ' + str(doi_item) + ' article not found in db')
                        citing_article = Article(doi=doi_item)
                        db.session.add(citing_article)
                        db.session.commit()
                    cited_article = Article.query.filter_by(doi=doi_item).first()
                    if Citation.query.filter_by(cited=cited_article.id,
                                                citing=article.id).first() is None:
                        citation = Citation(cited=cited_article.id,
                                            citing=article.id)
                        db.session.add(citation)
                        db.session.commit()'''

            # date = []
            date_inf = soup.find('span', class_='article-dates__first-online')
            year = int
            month = int
            day = int
            if date_inf is not None:
                date_time = date_inf.find('time')['datetime'].split('-')
                year = int(date_time.pop(0))
                month = int(date_time.pop(0))
                day = int(date_time.pop(0))
                # date = datetime.date(year=int(year), month=int(month), day=int(day))
                # article.pubdate = date
            log(self.thread_name() + ' ' + str(self.url) + ' date parsed')

            volume = ''
            issue = ''
            pp = ''
            number = ''
            if soup.find('a', class_='ArticleCitation_Issue') is not None:
                volume = soup.find('span', class_='ArticleCitation_Volume').get_text().replace(',', '\t')[6:]
                issue = soup.find('a', class_='ArticleCitation_Issue').get_text().replace(',', '\t')[5:]
                pp = soup.find('span', class_='ArticleCitation_Pages').get_text().replace(',', '\t')[3:]
                # article.volume = volume
                # article.issue = issue
                # article.pages = pp
            elif soup.find('span', class_='ArticleCitation_Volume') is not None:
                volume = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(0)
                issue = soup.find('time')['datetime'].split('-').pop(1).strip()
                if issue[0] == '0':
                    issue = issue[1:]
                number = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(1)
                # article.volume = volume
                # article.issue = issue
                # article.technical_info = number
            log(self.thread_name() + ' ' + str(self.url) + ' technical info parsed')

            if soup.find('span', class_='bibliographic-information__value', id='electronic-issn') is not None:
                ISSN = soup.find('span', class_='bibliographic-information__value', id='electronic-issn').get_text()
            else:
                ISSN = soup.find('span', class_='bibliographic-information__value', id='print-issn').get_text()
            # article.issn = ISSN
            log(self.thread_name() + ' ' + str(self.url) + ' ISSN parsed')

            journal = soup.find('div', class_='enumeration')
            journal_url = str(journal.find_all('a')[0]['href'])
            journal_title = str(journal.find_all('a')[0]['title'])
            journal_inf = {'title': codecs.encode(journal_title, 'translit/one'), 'url': codecs.encode(journal_url, 'translit/one')}
            # article.journal_id = Journal.query.filter_by(link='https://link.springer.com' + str(journal_url['href'])).first().id
            log(self.thread_name() + ' ' + str(self.url) + ' journal_id added to atrticle')

            key_section = soup.find('div', class_='KeywordGroup', lang="en")
            keywords = []
            if key_section is not None:
                for key_item in key_section.find_all('span', class_='Keyword'):
                    keywords.append(codecs.encode(key_item.get_text(), 'translit/one'))
            # article.keyword = keywords
            log(self.thread_name() + ' ' + str(self.url) + ' keywords parsed')

            authors = []
            aff = []
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
                        af_name.append(codecs.encode(af_dep + af_n + af_city + af_country, 'translit/one'))
                    '''for aff in af_name:
                        if Affilation.query.filter_by(aff=aff).first() is None:
                            new_aff = Affilation(aff=aff)
                            db.session.add(new_aff)
                            db.session.commit()'''

                # Check and add author
                for author_item in author_section.find_all('li', class_='u-mb-2 u-pt-4 u-pb-4'):
                    author_name = author_item.find('span', class_='authors-affiliations__name').get_text()
                    '''if Author.query.filter_by(name=author_name.get_text()).first() is None:
                        new_author = Author(name=author_name.get_text())
                        db.session.add(new_author)
                        db.session.commit()
                    # Select author in db
                    author_db = Author.query.filter_by(name=author_name.get_text()).first()'''
                    af_section = author_item.find('ul', class_='authors-affiliations__indexes u-inline-list')
                    if af_section is not None:
                        aff = [af_name[int(af_item.get_text()) - 1] for af_item in af_section.find_all('li')]
                    '''for af_item in af_section.find_all('li'):
                        new_aff = Affilation(aff=af_name[int(af_item.get_text()) - 1])
                        db.session.add(new_aff)
                        db.session.commit()
                        author_db.affilations.append(
                            new_aff) # Add affiiliation for author from aff_name by affiliation index
                        db.session.commit()'''
                    email_block = author_item.find('span', class_='author-information')
                    if email_block is not None:
                        email_name = email_block.find('a')['title']
                        if email_name is not None:
                            '''if Affilation.query.filter_by(aff=email_name).first() is None:
                                new_aff = Affilation(aff=email_name)
                                db.session.add(new_aff)
                                db.session.commit()
                            new_aff = Affilation.query.filter_by(aff=email_name).first()
                            author_db.affilations.append(new_aff)
                            db.session.commit()
                            article.authors.append(author_db)
                            db.session.commit()'''
                            aff.append(codecs.encode(email_name, 'translit/one'))
                    authors.append({'name': codecs.encode(author_name, 'translit/one'), 'aff': aff})
            # db.session.commit()
            log(self.thread_name() + ' ' + str(self.url) + ' authors and affiliations parsed')

            t = int(time.time())
            with open('Springer/' + journal_title, 'w', encoding='utf-8') as outfile:
                feeds.append({'journal': journal_inf,
                              'link': codecs.encode('https://link.springer.com' + self.url, 'translit/one'),
                              'title': codecs.encode(article_title, 'translit/one'),
                              'doi': codecs.encode(doi, 'translit/one'),
                              'abstract': codecs.encode(abstract, 'translit/one'),
                              'referenses': cited,
                              'date': {'day': day, 'month': month, 'year': year},
                              'volume': codecs.encode(volume, 'translit/one'),
                              'issue': codecs.encode(issue, 'translit/one'),
                              'pp': codecs.encode(pp, 'translit/one'),
                              'number': codecs.encode(number, 'translit/one'),
                              'ISSN': codecs.encode(ISSN, 'translit/one'),
                              'keywords': keywords,
                              'authors': authors})
                json.dump(feeds, outfile)
            req_time = int(time.time()) - t
            log(str(req_time) + ' ' + self.thread_name() + ' ' + str(self.url) + ' article added to file')

        except Exception as e:
            log('ERROR: ' + self.thread_name() + ' ' + str(self.url) + ' ' + str(e))

    def run(self):
        with app.app_context():
            while True:
                lock.acquire()
                if springer_parser.article_pool:
                    self.url = springer_parser.article_pool.pop()
                    springer_parser.try_articles += 1
                else:
                    self.url = ''
                lock.release()
                if self.url != '':
                    log(self.thread_name() + ' in ' + str(self.url))
                    self.get_article()
                    lock.acquire()
                    springer_parser.ready_articles += 1
                    lock.release()
                time.sleep(0.3)
