from . import Visualisation
import requests

class BigARTM(Visualisation):

    def __init__(self,data, layers):
        Visualisation.__init__(data)
        self.layers = layers

    def __fetchbigartmdata__(self):
        reponse = requests.get('')
