import time
from argparse import ArgumentParser
from Classes import keeper, TorInterface, Overwatch, Source, Miner, Worker
import os


user_agent = 'Googlebot'
headers = {
    'User-Agent': user_agent
    }


class SpringerParser(ArgumentParser):

    def __init__(self):
        ArgumentParser.__init__(self)
        self.miner_count = 100
        self.worker_count = 30
        self.name = 'SpringerParser'
        self.add_argument('-s', type=int)
        self.add_argument('-e', type=int)
        self.add_argument('-f', type=int)
        self.add_argument('-l', type=int)
        self.add_argument('-m', type=str)
        args = vars(self.parse_args())
        self.startt = args['s']
        self.end = args['e']
        self.years = range(args['f'], args['l'] + 1)
        self.mode = args['m']
        self.create()

    def create_tor_interface(self):
        tor_interface = TorInterface(controller='Not launched', password='1234')

    def create_overwatch(self):
        overwarch = Overwatch(mode=self.mode)

    def create_sources(self):
        if self.startt == 171:
            self.end = 175
        for i in range(int(self.startt), int(self.end + 1)):
            sourse = Source(name='Source-' + str(i), number=i)
            time.sleep(0.3)

    def create_miners(self):
        for i in range(int(self.miner_count)):
            miner = Miner(name='Miner-' + str(i + 1), years=self.years)
            time.sleep(0.3)

    def create_workers(self):
        for i in range(self.worker_count):
            worker = Worker(name='Worker-' + str(i + 1))
            time.sleep(0.3)

    def create(self):
        self.create_tor_interface()

        if self.mode == 'links':
            self.create_sources()
            time.sleep(5)
            self.create_overwatch()
            self.create_miners()
            while True:
                time.sleep(1)
        elif self.mode == 'articles':
            self.create_overwatch()
            keeper.file_list = os.listdir('/home/ubuntu/artanis/article_links/')
            keeper.dev = len(keeper.file_list) // self.worker_count
            self.create_workers()
            while True:
                time.sleep(1)
        else:
            raise ValueError('Unacceptable mode')
