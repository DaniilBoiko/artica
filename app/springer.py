import requests, datetime, sys, random, threading, time
from bs4 import BeautifulSoup
from app.models import Article, Citation, Author, Journal, Affilation
from app import db
from multiprocessing.dummy import Pool as ThreadPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app import app

user_agent = 'Googlebot'
headers = {'User-Agent': user_agent}

ready_list = []
proxy_list = []


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
    while n:
        create_proxies()
        try:
            response = requests.get('https://link.springer.com' + url, proxies=proxies)
            soup = BeautifulSoup(response.content, 'html.parser')

            article_title = soup.find('h1', class_='ArticleTitle').get_text()
            doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[
                  16:]
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

            date = []
            date = soup.find('span', class_='article-dates__first-online')
            if date is not None:
                date_time = date.find('time')['datetime'].split('-')
                year = date_time.pop(0)
                month = date_time.pop(0)
                day = date_time.pop(0)
                date = datetime.date(year=int(year), month=int(month), day=int(day))
                article.pubdate = date

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

            journal = soup.find('span', class_='JournalTitle').get_text()
            article.journal_id = Journal.query.filter_by(name=journal).first().id

            key_section = soup.find('div', class_='KeywordGroup', lang="en")
            keywords = []
            if key_section is not None:
                for key_item in key_section.find_all('span', class_='Keyword'):
                    keywords.append(key_item.get_text())
            article.keyword = keywords

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

            n = False

        except OSError:
            proxy_list.remove(proxy_item)


def get_journal(url):
    with app.app_context():
        i = True
        while i:
            create_proxies()
            try:
                response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + url, proxies=proxies)
                soup = BeautifulSoup(response.content, 'html.parser')
                journal_title = soup.find('div', id='publication-title').find('h1').get_text()

                if Journal.query.filter_by(name=journal_title).first() is None:
                    new_journal = Journal(name=journal_title, link='https://link.springer.com/journal/' + url,
                                          publisher='Springer')
                    db.session.add(new_journal)
                    db.session.commit()

                journal = Journal.query.filter_by(name=journal_title).first()

                issue_block = []
                volume_tab = soup.find('div', class_='volumes tab-content')
                for volume_item in volume_tab.find_all('div', class_='volume-item'):
                    issue_list = volume_item.find('ul', class_='issues-list')
                    for issue_item in issue_list.find_all('li', class_='issue-item'):
                        issue_block.append(issue_item.find('a', class_='title')['href'])

                k = False
                for issue_item in issue_block:
                    if journal.last_issue is not None:
                        if issue_item == journal.last_issue:
                            k = True

                    if (journal.last_issue is None) or k:
                        j = True
                        while j:
                            create_proxies()
                            try:
                                response = requests.get('https://link.springer.com' + issue_item, proxies=proxies)
                                soup = BeautifulSoup(response.content, 'html.parser')
                                results = soup.find('div', class_='toc')
                                for article_item in results.find_all('li'):
                                    article_link = article_item.find('h3', class_='title').find('a')['href']
                                    if Article.query.filter_by(doi=article_link[9:]).first() is None:
                                        get_article(article_link)
                                journal.last_issue = issue_item
                                db.session.commit()
                                j = False

                                k = True
                            except OSError:
                                proxy_list.remove(proxy_item)

                i = False
                ready_list.append(url)

            except OSError:
                proxy_list.remove(proxy_item)


class Overwatch(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        thread_dict = {}
        thread_list = []
        a = 1
        while len(ready_list) != len(links):
            if len(proxy_list) < 50:
                proxy_gen()
            print(time.strftime('%X'),
                  '  number of proxies: ', len(proxy_list), '  number of threads: ', threading.active_count(),
                  '  ready: ', len(ready_list) / len(links) * 100, '%')
            for item in threading.enumerate():
                if (item.ident in thread_list) is False:
                    thread_list.append(item.ident)
                    thread_dict['Thread-' + str(a)] = item.ident
                    a += 1
            time.sleep(10)


def get_springer(start, end):
    for item in range(int(start), int(end)):
        response = requests.get('https://link.springer.com/search/page/' + str(item) + '?facet-content-type="Journal"')
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find('ol', class_='content-item-list')
        global links
        links = []
        for result in results.find_all('li'):
            links.append(result.find('a')['href'][9:])
        observer = Overwatch()
        observer.start()
        pool_count = 50
        with ThreadPool(pool_count) as p:
            res = p.map(get_journal, links)
        observer.join()
