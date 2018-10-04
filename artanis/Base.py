import time
from multiprocessing import Process
import socks
import socket
from bs4 import BeautifulSoup
import requests
from stem import Signal
from stem.control import Controller


'''class BaseClass(threading.Thread):

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
            time.sleep(1)'''


headers = {
    'User-Agent': 'Googlebot'
    }


class TorInterface(Process):

    def __init__(self):
        Process.__init__(self)
        self.controller = "Not launched"
        self.password = "1234"
        self.start()

    def connect(self):
        self.controller = Controller.from_port(port=9051)
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "localhost", 9050, True)
        socket.socket = socks.socksocket
        print('Connection established')

    def renew_tor(self):
        self.controller.authenticate(self.password)
        self.controller.signal(Signal.NEWNYM)

    def show_ip(self):
        return BeautifulSoup(requests.get('http://www.showmyip.gr/').content, 'html.parser').find('span', {
            'class': 'ip_address'
            }).text.strip()

    def run(self):
        self.connect()
        while True:
            time.sleep(60)
            self.renew_tor()

