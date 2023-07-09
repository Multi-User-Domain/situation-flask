import json
import copy
import uuid
from flask import request, jsonify, send_file
from mud.utils import get_target_obj, get_recorded_history_for_event, prepare_action_changes
from config import app
from view_utils import get_headers, get_default_options_response
from users import users_blueprint
from characters import characters_blueprint
from cards import cards_blueprint
from worlds import worlds_blueprint
from ud import ud_blueprint

app.register_blueprint(users_blueprint)
app.register_blueprint(characters_blueprint, url_prefix='/characters')
app.register_blueprint(cards_blueprint, url_prefix='/cards')
app.register_blueprint(worlds_blueprint, url_prefix='/worlds')
app.register_blueprint(ud_blueprint, url_prefix='/ud')

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

'''
Routes for supporting complex behaviour in cards
'''

# TWT game jam endpoints
# the data passed isn't negotiated for now, it's always the full world data of the battle
# later we will want to support GET so that we can negotiate it using shapes
@app.route("/bogMonsterEatsVillager/", methods=["POST", "OPTIONS"])
def bog_monster_eats_villager():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)

    data = request.get_json()
    world_data = data["worldData"]
    action_data = data["actionData"]
    actor_data = data["actorData"]

    target = get_target_obj(world_data, action_data)
    result = {}

    # eat the first villager you find
    if "mudworld:hasPopulations" in target:
        for pop in target["mudworld:hasPopulations"]:
            if "mudworld:populationNumber" in pop and pop["mudworld:populationNumber"] > 0 and "mud:species" in pop and pop["mud:species"]["@id"] == "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mud.ttl#Human":
                pop["mudworld:populationNumber"] = pop["mudworld:populationNumber"] - 1
                if pop["mudworld:populationNumber"] == 0:
                    message = f"{actor_data['n:fn']} ate the last villager in the region {target['n:fn']}, now they are extinct!"
                else:
                    message = f"{actor_data['n:fn']} ate a villager from the region {target['n:fn']}"
                inserts = [
                    pop,
                    get_recorded_history_for_event(message)
                ]
                result = prepare_action_changes(action_data, [], inserts)
                break

    return jsonify(result), 200, get_headers({'Content-Type': 'application/ld+json'})
