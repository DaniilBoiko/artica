import json
import os
import time

'''
articles = 0
for file in os.listdir('/home/ubuntu/artanis/Springer'):
    try:
        with open('/home/ubuntu/artanis/Springer/' + file, 'r') as infile:
            articles += len(json.load(infile))
    except:
        ''
'''

links = 0
for file in os.listdir('/home/ubuntu/artanis/article_links/'):
    with open('/home/ubuntu/artanis/article_links/' + file, 'r') as infile:
        links += len(infile.readlines())


print(time.strftime('%X') + ' | articles ' + str(articles) + ' | links ' + str(links))