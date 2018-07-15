import requests
from bs4 import BeautifulSoup

user_agent = 'Googlebot'
headers = {'User-Agent': user_agent}

def get_article(url):
    response = requests.get('https://link.springer.com' + url)
    soup = BeautifulSoup(response.content, 'html.parser')

    title = soup.find('h1', class_='ArticleTitle').get_text()

    doi = soup.find('span', class_='bibliographic-information__value u-overflow-wrap', id='doi-url').get_text()[16:]
    #Проверяем наличие статьи в базе
    if doi is not None:
        article = Article.query.filter_by(doi=doi).first()
        if article is None:
            article = Article(doi=doi, title = title)
            db.session.add(article)
            db.session.commit()
        else:
            article.title = title
    else:
        article = Article.query.filter_by(title=title).first()
        if article is None:
            article = Article(doi=doi, title=title)
            db.session.add(article)
            db.session.commit()
    #проверили
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
            if Citation.query.filter_by(cited = cited_article.id,
                                        citing = article.id).first() is None:
                citation = Citation(cited = cited_article.id,
                                    citing = article.id)
                db.session.add(citation)
                db.session.commit()

    date = []
    date_time = soup.find('span', class_='article-dates__first-online')
    date = date_time.find('time')['datetime'].split('-')
    year = date.pop(0)
    month = date.pop(0)
    day = date.pop(0)
    date = datetime.date(year=year, month=month, day=day)
    article.pubdate = date

    if soup.find('a', class_='ArticleCitation_Issue') is not None:
        volume = soup.find('span', class_='ArticleCitation_Volume').get_text().replace(',', '\t')[6:]
        issue = soup.find('a', class_='ArticleCitation_Issue').get_text().replace(',', '\t')[5:]
        pp = soup.find('span', class_='ArticleCitation_Pages').get_text().replace(',', '\t')[3:]
        article.pages = pp
    elif soup.find('span', class_='ArticleCitation_Volume') is not None:
        volume = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(0)
        issue = soup.find('time')['datetime'].split('-').pop(1).strip()
        if issue[0] == '0':
            issue = issue[1:]
        number = soup.find('span', class_='ArticleCitation_Volume').get_text().split(':').pop(1)
        article.technical_info = number
    article.volume = volume
    article.issue = issue

    ISSN = soup.find('span', class_='bibliographic-information__value', id='electronic-issn').get_text()
    article.issn = ISSN

    journal = soup.find('span', class_='JournalTitle').get_text()

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
            af_section = author_item.find('ul', class_='authors-affiliations__indexes u-inline-list')
            for af_item in af_section.find_all('li'):
                af.append(af_item.get_text())
        for email_item in author_section.find_all('li', class_='u-mb-2 u-pt-4 u-pb-4'):
            email_block = email_item.find('span', class_='author-information')
            if email_block is not None:
                email_name = email_block.find('a')['title']
                emails.append(email_name)

        af_name_section = soup.find('ol', class_='test-affiliations')
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
                if Affiliation.query.filter_by(aff = aff) is None:
                    new_aff = Affiliarion(aff = aff)
