import os

import requests
from flask import Flask, make_response

app = Flask(__name__)
value = os.getenv("endpoint")

@app.route('/')
def hello_world():
    # 更改為 render_template
    res= requests.get(value, verify=False)
    reponse = make_response(res.text)
    return reponse

@app.route('/hello')
def hello():
    response = make_response('<h1>Hello, World!</h1>')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == '__main__':
    app.run(debug=True)