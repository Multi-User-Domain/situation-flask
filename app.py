import json
import copy
import uuid
from flask import request, jsonify, send_file
from config import db, app
from bson import json_util
from view_utils import get_headers, get_default_options_response
from users import users_blueprint
from characters import characters_blueprint
from cards import cards_blueprint
from worlds import worlds_blueprint
from ud import ud_blueprint
from items import items_blueprint
from actions import actions_blueprint

app.register_blueprint(users_blueprint)
app.register_blueprint(characters_blueprint, url_prefix='/characters')
app.register_blueprint(cards_blueprint, url_prefix='/cards')
app.register_blueprint(worlds_blueprint, url_prefix='/worlds')
app.register_blueprint(ud_blueprint, url_prefix='/ud')
app.register_blueprint(items_blueprint, url_prefix='/items')
app.register_blueprint(actions_blueprint, url_prefix='/actions')

@app.route("/.well-known/games-commons-configuration/")
def games_commons_configuration():
    return jsonify({
        "actionDiscovery": "https://simpolis.gamescommons.com/act/discover/"
    }), 200, get_headers({'Content-Type': 'application/json'})

@app.route("/act/discover/", methods=["POST"])
def action_discovery():
    jsonld = copy.deepcopy(request.get_json())
    return jsonify(json.loads(json_util.dumps(db.recipes.find(jsonld["target"]))))

@app.route("/")
def main():
    return "Hello world!", 200

@app.route("/images/<image_path>")
def image_uploaded(image_path):
    return send_file(f"./images/{image_path}", mimetype='image/png'), 200, get_headers()

@app.route("/ink/<file_path>")
def ink_uploaded(file_path):
    return send_file(f"./ink/{file_path}", mimetype='application/inkml+xml'), 200, get_headers()

@app.route("/content/sceneDescription/", methods=["POST", "OPTIONS"])
def scene_description():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    # TODO: include the agent who is perceiving the object
    return jsonify({
        "@context": {
            "mudcontent":"https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudcontent.ttl#"
        },
        "@id": "_CharacterSees",
        "mudcontent:sees": {
            "@id": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/examples/mudContentDescription.json",
            "@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudcontent.ttl#Content",
            "mudcontent:describes": "https://example.com/queenAnnesRevenge/",
            "mudcontent:hasText": "The Queen Anne's Revenge is an elegant sloop, swift and mouverable",
            "mudcontent:hasImage": "https://example.com/queenAnnesRevenge/"
        }
    }), 200, get_headers({'Content-Type': 'application/ld+json'})
