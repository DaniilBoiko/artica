import requests
from bs4 import BeautifulSoup
import translitcodec
import socks
import socket
import multiprocessing
from stem import Signal
from stem.control import Controller
import time
import codecs
import json


class TorInterface(multiprocessing.Process):

    def __init__(self, controller, password):
        multiprocessing.Process.__init__(self)
        self.controller = controller
        self.password = password
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
            language = soup.find('meta', attrs={'name': 'citation_language'})
            if language is not None:
                language = language['content']
            else:
                language = ''
            article_title = soup.find('h1', class_='ArticleTitle').get_text()
            doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[16:]
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
                             abstract=codecs.encode(abstract, 'translit/one'), referenses=cited, language=language, 
                        date={
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
