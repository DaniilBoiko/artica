from Multiprocessing import TorInterface, Overwatch, get_articles
from multiprocessing import Pool
import os


if __name__ == '__main__':

    tor_interface = TorInterface(controller='Not launched', password='1234')
    owerwatch = Overwatch()

    files = os.listdir('/home/ubuntu/artanis/article_links/')
    print(str(len(files)))

    pool = Pool(32)
    pool.map(get_articles, files)
