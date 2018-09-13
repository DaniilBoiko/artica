import threading
import time


class BaseClass(threading.Thread):
    
    def __init__( self, name ):
        threading.Thread.__init__(self)
        self.name = name
        self.log('started')
        self.lock = threading.Lock()
        self.start()
    
    def log( self, log ):
        ''
       # with open('logs', 'a') as logs:
           # logs.write(time.strftime('%X') + ' ' + self.name + ' ' + str(log) + '\n')
    
    def terminate( self ):
        raise RuntimeError()


class Keeper(BaseClass):
    
    def __init__( self ):
        self.years = []
        self.start_pool = 0
        self.pool = []
        self.times = []
        self.start_count = 0
        self.source_ready = 0
        self.errors = 0
        self.try_articles = 0
        self.ready_articles = 0
        self.file_list = [] 
        BaseClass.__init__(self, name='Keeper')
    
    def update( self, attr, value ):
        self.lock.acquire()
        if (type(value) is int) and type(self.__getattribute__(attr)) is list:
            value = [value]
        self.__setattr__(attr, self.__getattribute__(attr) + value)
        self.lock.release()
    
    def run( self ):
        while True:
            time.sleep(1)
