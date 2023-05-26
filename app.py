import json
import copy
import uuid
from flask import Flask, request, jsonify
#from rdflib import Graph
from urllib.parse import unquote_plus
from pymongo import MongoClient
from bson import json_util
from mud.vocab import MUD_CHAR

# config

app = Flask(__name__)

# TODO: environment variables
client = MongoClient('localhost', 27017)
db = client.situation
site_url = "https://api.realm.games.coop"

@app.route("/")
def main():
    return "Hello world!", 200

'''
@app.route("/character-templates/", methods=['GET'])
def character_templates():
    characters = list(db.character_templates.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, {'Content-Type': 'application/ld+json'}
'''

'''
REST endpoints for characters, cards, events, actions
'''

def _get_headers(extra_headers={}):
    headers = {
        'Access-Control-Allow-Origin': request.headers["Origin"],
        'Access-Control-Allow-Headers': 'access-control-allow-origin, content-type',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE',
        'Access-Control-Allow-Credentials': "true"
    }
    for header in extra_headers.keys():
        headers[header] = extra_headers[header]
    return headers

def _get_default_options_response(request):
    return jsonify({}), 200, _get_headers()

@app.route("/characters/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def characters():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())
        # TODO: data validation

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_CHAR.Character

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/characters/{str(uuid.uuid4())}/"

        db.characters.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, _get_headers({'Content-Type': 'application/ld+json'})
    
    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400

        db.characters.find_one_and_delete({
            {"@id": jsonld["@id"]}
        })

        return None, 204, _get_headers()

    characters = list(db.characters.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/cards/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def cards():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())
        # TODO: data validation

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_CHAR.Character

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/cards/{str(uuid.uuid4())}/"

        db.cards.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, _get_headers({'Content-Type': 'application/ld+json'})
    
    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        db.cards.find_one_and_delete({
            {"@id": jsonld["@id"]}
        })

        return None, 204, _get_headers()

    cards = list(db.cards.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(cards))), 200, _get_headers({'Content-Type': 'application/ld+json'})

'''
Routes for supporting complex behaviour in cards
'''

def _get_target_obj(world_data, action_data):
    '''
    gets the target object based on the action and the world data
    '''
    # current solution exploits implicit knowledge of the ontologies used in the game
    # TODO: consider using shapes or SPARQL for this, searching the object. GraphQL...?
    def _find_region_with_urlid(world_data, urlid):
        if world_data["@id"] == urlid:
            return world_data
        elif "mudworld:hasRegions" in world_data:
            for region in world_data["mudworld:hasRegions"]:
                res = _find_region_with_urlid(region, urlid)
                if res is not None:
                    return res
        return None

    target_id = action_data["mudcard:playTarget"]["@id"] if "@id" in action_data["mudcard:playTarget"] else None
    target_type = action_data["mudcard:playTarget"]["@type"]

    if target_type == "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudworld.ttl#Region":
        if target_id is not None:
            return _find_region_with_urlid(world_data, target_id)
        else:
            # TODO: allow for searching with shapes or SPARQL or owt, for less specific query
            pass

def _get_recorded_history_for_event(event_text):
    return {
        "@id": "_:RecordedHistory_" + str(uuid.uuid4()),
        "@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/games/twt2023.ttl#RecordedHistory",
        "n:hasNote": event_text
    }

def _prepare_action_changes(action_data, deletes=[], inserts=[]):
    return {
        "@context": {
            "n": "http://www.w3.org/2006/vcard/ns#",
            "mud": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mud#",
            "mudchar": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#",
            "mudcontent": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudcontent.ttl#",
            "mudlogic": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudlogic.ttl#",
            "mudcard": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudcard.ttl#"
        },
        "@id": action_data["@id"],
        "@type": action_data["@type"], 
        "mudlogic:patchesOnComplete": {
            "@id": "_:endState",
            "@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudlogic.ttl#Patch",
            "mudlogic:deletes": deletes,
            "mudlogic:inserts": inserts
        }
    }

# TWT game jam endpoints
# the data passed isn't negotiated for now, it's always the full world data of the battle
# later we will want to support GET so that we can negotiate it using shapes
@app.route("/bogMonsterEatsVillager/", methods=["POST", "OPTIONS"])
def bog_monster_eats_villager():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)

    data = request.get_json()
    world_data = data["worldData"]
    action_data = data["actionData"]
    actor_data = data["actorData"]

    target = _get_target_obj(world_data, action_data)
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
                    _get_recorded_history_for_event(message)
                ]
                result = _prepare_action_changes(action_data, [], inserts)
                break

    return jsonify(result), 200, _get_headers({'Content-Type': 'application/ld+json'})
