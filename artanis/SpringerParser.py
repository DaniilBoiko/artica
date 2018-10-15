import time
from argparse import ArgumentParser
import translitcodec
import codecs
import json
import requests
from bs4 import BeautifulSoup
from multiprocessing import Process, Pool
import os
from Base import headers, TorInterface


def get_links(page):

	pool = []
	page_link = str('https://link.springer.com/search/page/' + str(page[0]) + '?facet-content-type="Journal')

	response = requests.get(page_link)
	results = BeautifulSoup(response.content, 'html.parser').find('ol', class_='content-item-list')
	pool += [result.find('a')['href'][9:] for result in results.find_all('li')]

	for journal in pool:

		try:
			response = requests.get('https://link.springer.com/journal/volumesAndIssues/' + str(journal), timeout=60)
			soup = BeautifulSoup(response.content, 'html.parser')
			journal_title = soup.find('div', id='publication-title').find('h1').get_text()
			issue_block = []
			volume_tab = soup.find('div', class_='volumes tab-content')
			for volume_item in volume_tab.find_all('div', class_='volume-item'):
				for issue_item in volume_item.find('ul', class_='issues-list').find_all('li', class_='issue-item'):
					issue_year = int(issue_item.find('a', class_='title').get_text().split(',')[0].split(' ')[-1])
					if issue_year in page[1]:
						issue_block.append(issue_item.find('a', class_='title')['href'])
			for issue in issue_block:
				response = requests.get('https://link.springer.com' + issue, timeout=60)
				soup = BeautifulSoup(response.content, 'html.parser')
				for article_item in soup.find('div', class_='toc').find_all('li'):
					article_link = article_item.find('h3', class_='title').find('a')['href']
					with open('Springer_links/' + str(journal_title).replace(' ', '_'), 'a') as outfile:
						outfile.write(codecs.encode(article_link, 'translit/one') + '\n')
					print(article_link)
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
						with open('Springer_links/' + str(journal_title).replace(' ', '_'), 'a') as outfile:
							outfile.write(codecs.encode(article_link, 'translit/long') + '\n')
						print(article_link)

		except Exception as e:
			with open('except_issues', 'a') as outfile:
				outfile.write(codecs.encode(str(journal), 'translit/one') + ' ' + str(e) + '\n')


def get_articles(file):

	with open('Springer_links/' + file, 'r') as datafile:
		links = datafile.readlines()

	while links:

		url = links.pop()
		text = ''
		for link in links:
			text += str(link)
		with open('Springer_links/' + file, 'w') as datafile:
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
							cited.append(codecs.encode(ref_doi.find('a', class_='gtm-reference')['href'][16:],
													   'translit/one'))
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
				outfile.write(codecs.encode(str(url), 'translit/one') + ' ' + str(e) + '\n')


if __name__ == '__main__':

	tor_interface = TorInterface()

	args = ArgumentParser()
	args.add_argument('-m', type=str)
	args.add_argument('-s', type=int)
	args.add_argument('-e', type=int)
	mode = vars(args.parse_args())['m']
	start = vars(args.parse_args())['s']
	end = vars(args.parse_args())['e']

	if mode == 'links':
		pool = Pool(32)
		years = [year for year in range(int(start), int(end)+1)]
		pages = [(page, years) for page in range(1, 176)]
		pool.map(get_links, pages)

	elif mode == 'articles':
		pool = Pool(32)
		files = os.listdir('article_links')
		pool.map(get_articles, files)

	else:
		raise ValueError('Unacceptable mode')

