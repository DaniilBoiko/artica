import translitcodec
import codecs
import json
import requests
import socket
import socks
import time
from bs4 import BeautifulSoup
from stem import Signal
from stem.control import Controller
import os
from multiprocessing import Process, Pool
from argparse import ArgumentParser
from Base import TorInterface, headers


def get_journals():
    response = requests.get('https://pubs.acs.org/', headers=headers, timeout=60)
    soup = BeautifulSoup(response.content, 'html.parser')
    content = soup.find('div', class_='az-list')
    journal_lists = content.find_all('ul')
    journals = ''
    for journal_list in journal_lists:
        for journal in journal_list.find_all('li'):
            if journal.find('a')['href'][:2] == '/j':
                journals += (str(journal.find('a')['href']) + '\n')
    with open('ACS_journals', 'a') as outfile:
        outfile.write(journals)


def get_issues(url):
    response = requests.get('https://pubs.acs.org/loi/' + url, headers=headers, timeout=60)
    soup = BeautifulSoup(response.content, 'html.parser')
    volume_list = soup.find('article', class_='volume-list')
    links = ''
    for volume in volume_list.find_all('div', class_='slider'):
        for issue in volume.find_all('div', class_='row'):
            links += (issue.find('a')['href'] + '\n')
    with open('ACS_issues/' + url, 'a') as outfile:
        outfile.write(links)


def get_article_links(file):
    with open('ACS_issues/' + file, 'r') as datafile:
        urls = datafile.readlines()
    while urls:
        url = urls.pop()
        text = ''
        for item in urls:
            text += str(item)
        with open('ACS_issues/' + file, 'w') as datafile:
            datafile.write(text)
        if url[:2] == 'ht':
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            journal_title = soup.find('head').find('title').get_text()
            links = ''
            for link in soup.find_all('div', class_='DOI'):
                links += (link.get_text() + '\n')
            with open('ACS_article_links/' + journal_title, 'a') as outfile:
                outfile.write(links)


def get_article(file):
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
        affiliations = soup.find('div', class_='affiliations')
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
                         pp=codecs.encode(pp, 'translit/one'), authors=authors)))


if __name__ == '__main__':

    tor_insterface = TorInterface()

    args = ArgumentParser()
    args.add_argument('-m', type=str)
    mode = vars(args.parse_args())['m']

    if mode == 'jl':
        get_journals()

    elif mode == 'il':
        pool = Pool(32)
        with open('ACS_journals', 'r') as file:
            data = file.readlines()
        pool.map(get_issues, [url[9:].replace('\n', '') for url in data])

    elif mode == 'al':
        pool = Pool(32)
        pool.map(get_article_links, os.listdir('ACS_issues'))

    elif mode == 'a':
        pool = Pool(32)
        pool.map(get_article, os.listdir('ACS_article_links'))

    else:
        raise ValueError('Unacceptable mode')
