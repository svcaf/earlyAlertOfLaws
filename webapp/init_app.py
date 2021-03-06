from elasticsearch import Elasticsearch
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

def create_app():
    app = Flask(__name__)
    app.elasticsearch = Elasticsearch('http://localhost:9200', http_compress=True)
    
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bills.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

app = create_app()
db = SQLAlchemy(app)