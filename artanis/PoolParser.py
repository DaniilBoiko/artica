from Multiprocessing import TorInterface, get_articles
from multiprocessing import Pool
import os


if __name__ == '__main__':

    tor_interface = TorInterface(controller='Not launched', password='1234')

    files = os.listdir('article_links/')

    pool = Pool(32)
    pool.map(get_articles, files)
