import json
from datetime import datetime
from flask import Flask, request, jsonify
#from rdflib import Graph
from urllib.parse import unquote_plus
#from pymongo import MongoClient
from bson import json_util

# config

app = Flask(__name__)

#client = MongoClient('localhost', 27017)
#db = client.situation

@app.route("/")
def main():
    return None, 204

'''
@app.route("/character-templates/", methods=['GET'])
def character_templates():
    characters = list(db.character_templates.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, {'Content-Type': 'application/ld+json'}
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
        "@id": "_:RecordedHistory_" + str(datetime.now()),
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
@app.route("/bogMonsterEatsVillager/", methods=["POST"])
def bog_monster_eats_villager():
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
                deletes = [
                    pop
                ]
                pop["mudworld:populationNumber"] = pop["mudworld:populationNumber"] - 1
                if pop["mudworld:populationNumber"] == 0:
                    message = f"{actor_data['n:fn']} ate the last villager in the region {target['n:fn']}, now they are extinct!"
                else:
                    message = f"{actor_data['n:fn']} ate a villager from the region {target['n:fn']}"
                inserts = [
                    pop,
                    _get_recorded_history_for_event(message)
                ]
                result = _prepare_action_changes(action_data, deletes, inserts)
                break

    return jsonify(result), 200, {'Content-Type': 'application/ld+json'}
