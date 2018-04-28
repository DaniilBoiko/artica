from flask import render_template, request, redirect, url_for, jsonify
from app import app
from app import db
from app import q, Job, conn

def parseXMLs():
    result = []
    return result

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query')
    return render_template('search.html', title='Home',query=query)


@app.route('/admin', methods=['GET'])
def admin():
    token = request.args.get('token')
    if token != '64E80F015881BF456198E9DAECB22B23D52CC45E2DE4708780E20F0E28F76CB0':
        return redirect(url_for('index'))

    if request.args.get('task') is not None:
        if request.args.get('task') == 'parseXML':
            job = q.enqueue_call(
                func=parseXMLs, args=(), result_ttl=50000
            )
            print(job.get_id())

    return render_template('admin.html', title='admin')


@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):

    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        return str(job.result), 200
    else:
        return "Nay!", 202
