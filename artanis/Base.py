import threading
import time
import os


class BaseClass(threading.Thread):

    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.lock = threading.Lock()
        self.start()


class Keeper(BaseClass):

    def __init__(self):
        self.pool = []
        self.ready_articles = 0
        self.ready_journals = 0
        self.ready_errors = 0
        self.errors = 0
        self.file_list = []
        self.dev = 0
        BaseClass.__init__(self, name='Keeper')

    def run(self):
        while True:
            time.sleep(1)
