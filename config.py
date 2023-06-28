from flask import Flask
from pymongo import MongoClient


# config
# TODO: environment variables

app = Flask(__name__)
client = MongoClient('localhost', 27017)
db = client.situation
site_url = "https://api.realm.games.coop"
