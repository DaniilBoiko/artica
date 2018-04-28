from flask import render_template, request
from app import app


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')


@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.args.get('query')
    return render_template('search.html', title='Home',query=query)