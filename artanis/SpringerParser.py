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
        self.miner_count = 30
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
        keeper.years = range(args['f'], args['l'] + 1)
        self.mode = args['m']
        self.create()
    
    def create_tor_interface(self):
        tor_interface = TorInterface(controller='Not launched', password='1234')
    
    def create_overwatch(self):
        overwarch = Overwatch()
    
    def create_sources(self):
        for i in range(int(self.startt), int(self.end + 1)):
            sourse = Source(name='Source-' + str(i), number=i)
            time.sleep(0.3)
    
    def create_miners(self):
        for i in range(int(self.miner_count)):
            miner = Miner(name='Miner-' + str(i + 1))
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
            keeper.file_list = [file for file in os.walk('article_links')][0][2]
            self.create_workers()
            while True:
                time.sleep(1)
        else:
            raise ValueError('Unacceptable mode')
