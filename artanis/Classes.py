import translitcodec
import codecs
import json
import requests
import socket
import socks
import threading
import time
from Base import BaseClass
from artanis import keeper
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
import os
from multiprocessing import Process, Pool
from argparse import ArgumentParser


class TorInterface(BaseClass):
    
    def __init__(self):
        self.controller = 'Not launched'
        self.password = '1234'
        BaseClass.__init__(self, name='TorInterface')
    
    def connect(self):
        self.controller = Controller.from_port(port=9051)
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 9050, True)
        socket.socket = socks.socksocket
        print('Connection established')
    
    def renew_tor(self):
        self.lock.acquire()
        self.controller.authenticate(self.password)
        self.controller.signal(Signal.NEWNYM)
        self.lock.release()
    
    def show_ip(self):
        return BeautifulSoup(requests.get('http://www.showmyip.gr/').content, 'html.parser').find('span', {
            'class': 'ip_address'
            }).text.strip()
    
    def run(self):
        self.connect()
        while True:
            time.sleep(60)
            self.renew_tor()


class TorInterface(Process):

    def __init__(self):
        Process.__init__(self)
        self.controller = "Not launched"
        self.password = "1234"
        self.start()

    def connect(self):
        self.controller = Controller.from_port(port=9051)
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 9050, True)
        socket.socket = socks.socksocket
        print('Connection established')

    def renew_tor(self):
        self.controller.authenticate(self.password)
        self.controller.signal(Signal.NEWNYM)

    def show_ip(self):
        return BeautifulSoup(requests.get('http://www.showmyip.gr/').content, 'html.parser').find('span', {
            'class': 'ip_address'
            }).text.strip()

    def run(self):
        self.connect()
        while True:
            time.sleep(60)
            self.renew_tor()


class Overwatch(BaseClass):
    
    def __init__(self, mode):
        self.mode = mode
        BaseClass.__init__(self, name='Overwatch')
    
    def run(self):
        if self.mode == 'articles':
            while True:
                links = 0
                for file in os.listdir('article_links'):
                    with open('article_links/' + file, 'r') as infile:
                        links += len(infile.readlines())
                print(time.strftime('%X') + ' | links ' + str(links))
                with open('times', 'a') as file:
                    file.write(str(links) + '\n')
                time.sleep(60)
        if self.mode == 'links':
            while True:
                print(time.strftime('%X') + ' | journals ' + str(keeper.ready_journals))
                time.sleep(10)


class Source(BaseClass):

    def __init__(self, name, number):
        self.number = number
        BaseClass.__init__(self, name=name)

    def run(self):
        page_link = str('https://link.springer.com/search/page/' + str(self.number) + '?facet-content-type="Journal')
        response = requests.get(page_link)
        results = BeautifulSoup(response.content, 'html.parser').find('ol', class_='content-item-list')
        self.lock.acquire()
        keeper.pool += [result.find('a')['href'][9:] for result in results.find_all('li')]
        self.lock.release()


class Miner(BaseClass):

    def __init__(self, name, years):
        self.urls = []
        self.url = ''
        self.years = years
        BaseClass.__init__(self, name=name)

    def get_article_links(self, url):
        try:
            response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + str(url), timeout=60)
            soup = BeautifulSoup(response.content, 'html.parser')
            journal_title = soup.find('div', id='publication-title').find('h1').get_text()
            issue_block = []
            volume_tab = soup.find('div', class_='volumes tab-content')
            for volume_item in volume_tab.find_all('div', class_='volume-item'):
                for issue_item in volume_item.find('ul', class_='issues-list').find_all('li', class_='issue-item'):
                    issue_year = int(issue_item.find('a', class_='title').get_text().split(',')[0].split(' ')[-1])
                    if issue_year in self.years:
                        issue_block.append(issue_item.find('a', class_='title')['href'])
            for issue in issue_block:
                response = requests.get('https://link.springer.com' + issue, timeout=60)
                soup = BeautifulSoup(response.content, 'html.parser')
                for article_item in soup.find('div', class_='toc').find_all('li'):
                    article_link = article_item.find('h3', class_='title').find('a')['href']
                    with open('article_links/' + str(journal_title).replace(' ', '_'), 'a') as outfile:
                        outfile.write(codecs.encode(article_link, 'translit/one') + '\n')
                # issue pages counter
                art_number = soup.find('div', class_='toc').find('h2').find('span').get_text().split(' ')[0][1:]
                pages = int(art_number) // 20
                for item in range(0, pages):
                    issue_link = ''
                    for i in range(1, (len(issue.split('/')) - 1)):
                        issue_link += ('/' + str(issue.split('/')[i]))
                    issue_link += ('/' + str(int(issue.split('/')[(len(issue.split('/')) - 1)]) + item))
                    response = requests.get('https://link.springer.com' + issue_link, timeout=60)
                    results = BeautifulSoup(response.content, 'html.parser').find('div', class_='toc')
                    for article_item in results.find_all('li'):
                        article_link = article_item.find('h3', class_='title').find('a')['href']
                        journal_title = str(journal_title).replace(' ', '_')
                        with open('article_links/' + str(journal_title).replace(' ', '_'), 'a') as outfile:
                            outfile.write(codecs.encode(article_link, 'translit/long') + '\n')
            keeper.ready_journals += 1
        
        except Exception as e:
            keeper.errors += 1
            with open('except_issues', 'a') as outfile:
                outfile.write(codecs.encode(str(url), 'translit/one') + '\n')
    
    def run(self):
        self.lock.acquire()
        for i in range(35):
            if keeper.pool:
                self.urls.append(keeper.pool.pop())
        self.lock.release()
        while True:
            if self.urls:
                self.url = self.urls.pop()
                self.get_article_links(url=self.url)
            time.sleep(0.3)


def get_articles(file):
    with open('article_links/' + file, 'r') as datafile:
        links = datafile.readlines()
    
    while links:
        
        url = links.pop()
        text = ''
        for link in links:
            text += str(link)
        with open('article_links/' + file, 'w') as datafile:
            datafile.write(text)
        
        try:
            response = requests.get('https://link.springer.com' + url, timeout=60)
            soup = BeautifulSoup(response.content, 'html.parser')
            language = soup.find('meta', attrs={
                'name': 'citation_language'
                })
            if language is not None:
                language = language['content']
            else:
                language = ''
            article_title = soup.find('h1', class_='ArticleTitle').get_text()
            doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[
                  16:]
            abstract = ''
            abstract_section = soup.find('section', class_='Abstract')
            if abstract_section is not None:
                for abstract_par in abstract_section.find_all('p'):
                    abstract = abstract + abstract_par.get_text() + '\n'
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
                            cited.append(
                                codecs.encode(ref_doi.find('a', class_='gtm-reference')['href'][16:], 'translit/one'))
            date_inf = soup.find('span', class_='article-dates__first-online')
            year = ''
            month = ''
            day = ''
            if date_inf is not None:
                date_time = date_inf.find('time')['datetime'].split('-')
                year = str(date_time.pop(0))
                month = str(date_time.pop(0))
                day = str(date_time.pop(0))
            volume = ''
            issue = ''
            pp = ''
            number = ''
            if soup.find('a', class_='ArticleCitation_Issue') is not None:
                volume = soup.find('span', class_='ArticleCitation_Volume').get_text().replace(',', '\t')[6:]
                issue = soup.find('a', class_='ArticleCitation_Issue').get_text().replace(',', '\t')[5:]
                pp = soup.find('span', class_='ArticleCitation_Pages').get_text().replace(',', '\t')[3:]
            elif soup.find('span', class_='ArticleCitation_Volume') is not None:
                volume = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(0)
                issue = soup.find('time')['datetime'].split('-').pop(1).strip()
                if issue[0] == '0':
                    issue = issue[1:]
                number = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(1)
            if soup.find('span', class_='bibliographic-information__value', id='electronic-issn') is not None:
                issn = soup.find('span', class_='bibliographic-information__value', id='electronic-issn').get_text()
            else:
                issn = soup.find('span', class_='bibliographic-information__value', id='print-issn').get_text()
            journal = soup.find('div', class_='enumeration')
            journal_url = str(journal.find_all('a')[0]['href'])
            journal_title = str(journal.find_all('a')[0]['title'])
            journal_inf = {
                'title': codecs.encode(journal_title, 'translit/one'),
                'url': codecs.encode(journal_url, 'translit/one')
                }
            key_section = soup.find('div', class_='KeywordGroup', lang="en")
            keywords = []
            if key_section is not None:
                for key_item in key_section.find_all('span', class_='Keyword'):
                    keywords.append(codecs.encode(key_item.get_text(), 'translit/one'))
            key_section = soup.find('div', class_='KeywordGroup', lang="en")
            keywords = []
            if key_section is not None:
                for key_item in key_section.find_all('span', class_='Keyword'):
                    keywords.append(codecs.encode(key_item.get_text(), 'translit/one'))
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
                for author_item in author_section.find_all('li', class_='u-mb-2 u-pt-4 u-pb-4'):
                    author_name = author_item.find('span', class_='authors-affiliations__name').get_text()
                    af_section = author_item.find('ul', class_='authors-affiliations__indexes u-inline-list')
                    if af_section is not None:
                        aff = [af_name[int(af_item.get_text()) - 1] for af_item in af_section.find_all('li')]
                    email_block = author_item.find('span', class_='author-information')
                    if email_block is not None:
                        email_name = email_block.find('a')['title']
                        if email_name is not None:
                            aff.append(codecs.encode(email_name, 'translit/one'))
                    authors.append({
                        'name': codecs.encode(author_name, 'translit/one'),
                        'aff': aff
                        })
            
            data = dict(journal=journal_inf, link=codecs.encode('https://link.springer.com' + url, 'translit/one'),
                        title=codecs.encode(article_title, 'translit/one'), doi=codecs.encode(doi, 'translit/one'),
                        abstract=codecs.encode(abstract, 'translit/one'), referenses=cited, language=language, date={
                    'day': day,
                    'month': month,
                    'year': year
                    }, volume=codecs.encode(volume, 'translit/one'), issue=codecs.encode(issue, 'translit/one'),
                        pp=codecs.encode(pp, 'translit/one'), number=codecs.encode(number, 'translit/one'),
                        ISSN=codecs.encode(issn, 'translit/one'), keywords=keywords, authors=authors)
            with open('Springer/' + journal_title, 'a') as outfile:
                outfile.write(json.dumps(data) + '\n')
        
        except Exception as e:
            with open('except_articles', 'a') as outfile:
                outfile.write(codecs.encode(str(url), 'translit/one') + '\n')

'''
class ACSParser(ArgumentParser):
  
    def __init__(self):
        

    
    
    

    def get_article_links(self, file):
        with open('ACS_issues/' + file, 'r') as datafile:
            links = datafile.readlines()
        while links:
            url = links.pop()
            text = ''
            for link in links:
                text += str(link)
            with open('ACS_issues/' + file, 'w') as datafile:
                datafile.write(text)
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            journal_title = soup.find('head').find('title').get_text()
            links = ''
            for link in soup.find_all('div', class_='DOI'):
                links += (link.get_text() + '\n')
            with open('ACS_article_links/' + journal_title, 'a') as outfile:
                outfile.write(links)

    def get_article(self, file):
        with open('ACS_article_links/' + file, 'r') as datafile:
            links = datafile.readlines()
            journal_url = file
        while links:
            url = links.pop().replace('\n', '')
            text = ''
            for link in links:
                text += str(link)
            with open('ACS_article_links/' + file, 'w') as datafile:
                datafile.write(text)
            response = requests.get('https://pubs.acs.org/doi/' + url, timeout=60)
            soup = BeautifulSoup(response.content, 'html.parser')
            language = soup.find('meta', attrs={
                'name': 'dc.Language'
                })
            if language is not None:
                language = language['content']
            else:
                language = ''
            article_title = soup.find('meta', attrs={
                'name': 'dc.Title'
                })
            if article_title is not None:
                article_title = article_title['content']
            else:
                article_title = ''
            doi = url
            abstract = ''
            blocks = soup.find_all('p', class_='articleBody_abstractText')
            if blocks:
                for block in blocks:
                    abstract += block.get_text()
            months_dict = {
                'January': 1,
                'February': 2,
                'March': 3,
                'April': 4,
                'May': 5,
                'June': 6,
                'July': 7,
                'August': 8,
                'September': 9,
                'October': 10,
                'November': 11,
                'December': 12
                }
            date = soup.find('meta', attrs={
                'name': 'dc.Date'
                })
            if date is not None:
                date = date['content'].split(' ')
                date = {
                    'day': date[1].replace(',', ''),
                    'month': months_dict[date[0]],
                    'year': date[2]
                    }
            else:
                date = ''
            volume = soup.find('span', class_='citation_volume')
            if volume is not None:
                volume = volume.get_test()
            else:
                volume = ''
            issue = soup.find('div', id='citation')
            if issue is not None:
                issue = issue.get_text().split('(')[1].split(')')[0]
            else:
                issue = ''
            pp = soup.find('div', id='citation')
            if pp is not None:
                pp = pp.get_text().split('pp ')[1]
            else:
                pp = ''
            authors = []
            author_block = soup.find('div', id='authors')
            if author_block is not None:
                for author in author_block.find_All('span', class_='hlFld-ContribAuthor'):
                    authors.append({
                        'name': author.find_all('a')[0].get_text(),
                        'aff': [aff.get_text() for aff in author.find_all('a')[1:-1]]
                        })
            affiliations = soup.find('div', class_='assiliations')
            if affiliations is not None:
                for aff_item in affiliations.find_all('div'):
                    aff = aff_item.find('sup')
                    if aff is not None:
                        aff = aff.get_text() + ', '
                    else:
                        aff = ''
                    institution = aff_item.find('span', class_='institution')
                    if institution is not None:
                        institution = institution.get_text() + ', '
                    else:
                        institution = ''
                    addr_line = aff_item.find('span', class_='addr-line')
                    if addr_line is not None:
                        addr_line = addr_line.get_text() + ', '
                    else:
                        addr_line = ''
                    region = aff_item.get_text()
                    if region is not None:
                        region = region.replace(',', '').replace(' ', '') + ', '
                    else:
                        region = ''
                    code = aff_item.find('postal_code')
                    if code is not None:
                        code = code.get_text() + ', '
                    else:
                        code = ''
                    city = aff_item.find('city')
                    if city is not None:
                        city = city.get_text() + ', '
                    else:
                        city = ''
                    country = aff_item.find('span', class_='country')
                    if country is not None:
                        country = country.get_text()
                    else:
                        country = ''
                    affiliation = {
                        'aff': aff,
                        'address': codecs.encode(institution + addr_line + region + code + city + country,
                                                 'tranclit/one')
                        }
            journal_title = soup.find('meta', attrs={
                'name': 'citation_journal_title'
                }).get_text()
            journal_inf = {
                'title': codecs.encode(journal_title, 'translit/one'),
                'url': codecs.encode(journal_url, 'translit/one')
                }
            with open('ACS/' + journal_title, 'a') as outfile:
                outfile.write(json.dumps(
                        dict(journal=journal_inf, link=codecs.encode('https://link.springer.com' + url, 'translit/one'),
                             title=codecs.encode(article_title, 'translit/one'), doi=codecs.encode(doi, 'translit/one'),
                             abstract=codecs.encode(abstract, 'translit/one'),
                             language=codecs.encode(language, 'translit/one'), date=date,
                             volume=codecs.encode(volume, 'translit/one'), issue=codecs.encode(issue, 'translit/one'),
                             pp=codecs.encode(pp, 'translit/one'), authors=authors)))'''