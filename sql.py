import psycopg2
import json
conn = psycopg2.connect(host="artica.caur5thdijuo.us-east-2.rds.amazonaws.com",database="artica", user="artica", password="keklolkek")
cur = conn.cursor()
cur.execute("SELECT id, title FROM datasets_document WHERE dataset_id = 15")
rows = cur.fetchall()
dictionary = {}
for row in rows:
    dictionary[row[0]] = row[1]
with open ('data.txt', 'w') as f:
    f.write(json.dumps(dictionary))
