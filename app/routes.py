from flask import render_template, request, redirect, url_for
from app import app


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
    return render_template('admin.html', title='admin')