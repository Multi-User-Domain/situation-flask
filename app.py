import json
from flask import Flask, request, jsonify
from rdflib import Graph
from urllib.parse import unquote_plus
from pymongo import MongoClient
from bson import json_util

# config

app = Flask(__name__)

client = MongoClient('localhost', 27017)
db = client.situation

@app.route("/")
def main():
    return None, 204

@app.route("/character-templates/", methods=['GET'])
def character_templates():
    characters = list(db.character_templates.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, {'Content-Type': 'application/ld+json'}
