import json
import os
import time

'''
articles = 0
for file in os.listdir('Springer'):
    try:
        with open('Springer/' + file, 'r') as infile:
            articles += len(json.load(infile))
    except:
        ''
'''
while True:
    links = 0
    for file in os.listdir('article_links'):
        with open('article_links/' + file, 'r') as infile:
            links += len(infile.readlines())    
    print(time.strftime('%X') + ' | links ' + str(links))
    time.sleep(60)
