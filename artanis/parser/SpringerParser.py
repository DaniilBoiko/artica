import threading
import time
from argparse import ArgumentParser


user_agent = 'Googlebot'
headers = {
	'User-Agent': user_agent
	}


class BaseClass(threading.Thread):
	
	def __init__(self, name):
		threading.Thread.__init__(self)
		self.name = name
		self.log('started')
		self.lock = threading.Lock()
		self.start()
	
	def log(self, log):
		with open('logs', 'a') as logs:
			logs.write(time.strftime('%X') + ' ' + self.name + ' ' + str(log) + '\n')
	
	def terminate(self):
		raise RuntimeError()


class SpringerParser(BaseClass, ArgumentParser):
	
	def __init__(self):
		ArgumentParser.__init__(self)
		self.time_start = int(time.time())
		self.source_count = 0
		self.miner_count = 30
		self.worker_count = 30
		self.pool = []
		self.times = []
		self.errors = 0
		self.try_articles = 0
		self.ready_articles = 0
		self.flag = False
		self.add_argument('-s', type=int)
		self.add_argument('-e', type=int)
		self.add_argument('-f', type=int)
		self.add_argument('-l', type=int)
		self.add_argument('-m', type=str)
		args = vars(self.parse_args())
		self.startt = args['s']
		self.end = args['e']
		self.years = [args['f'], args['l']]
		self.mode = args['m']
		BaseClass.__init__(self, name='SpringerParser')
	
	def create_tor_interface(self):
		from .Springer import TorInterface
		tor_interface = TorInterface(controller='Not launched', password='1234')
	
	def update(self, attr, value):
		self.lock.acquire()
		self.__setattr__(attr, self.__getattribute__(attr) + value)
		self.lock.release()
		
	
	def create_overwatch(self):
		from .Springer import Overwatch
		overwatch = Overwatch()
	
	def create_sources(self):
		from .Springer import Source
		for i in range(int(self.startt), int(self.end)):
			self.update('source_count', 1)
			source = Source(name='Source-' + str(i), number=i)
			time.sleep(0.3)
	
	def create_miners(self):
		from .Springer import Miner
		for i in range(int(self.miner_count)):
			miner = Miner(name='Miner-' + str(i + 1))
			time.sleep(0.3)
	
	def create_workers(self):
		from .Springer import Worker
		for i in range(self.worker_count):
			worker = Worker(name='Worker-' + str(i + 1))
			time.sleep(0.3)
	
	def run(self):
		self.create_tor_interface()
		self.create_overwatch()
		
		if self.mode == 'links':
			self.create_sources()
			while self.source_count != 0:
				time.sleep(1)
			self.log('Sourses are off')
			self.create_miners()
		elif self.mode == 'articles':
			while True:
				self.create_workers()
				time.sleep(600)
				self.flag = True
				time.sleep(20)
				self.flag = False
		else:
			raise ValueError('Unacceptable mode')
		
