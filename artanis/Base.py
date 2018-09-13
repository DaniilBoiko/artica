import threading
import time


class BaseClass(threading.Thread):
    
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        #self.log('started')
        self.lock = threading.Lock()
        self.start()
    
    '''def log(self, log):
        with open('logs', 'a') as logs:
            logs.write(time.strftime('%X') + ' ' + self.name + ' ' + str(log) + '\n')'''


class Keeper(BaseClass):
    
    def __init__(self):
        self.years = []
        self.pool = []
        self.times = []
        self.errors = 0
        self.try_articles = 0
        self.ready_articles = 0
        self.file_list = []
        BaseClass.__init__(self, name='Keeper')
    
    def run(self):
        while True:
            time.sleep(1)
