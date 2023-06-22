import json
import copy
import uuid
import base64
import syslog
import io
from flask import Flask, request, jsonify, send_file, Response
from rdflib import Graph
from pyshacl import validate
from urllib.parse import urlparse
from urllib.request import urlopen
from PIL import Image
from pymongo import MongoClient
from bson import json_util
from mud.vocab import MUD_ACCT, MUD_CHAR, MUD_DIALOGUE, MUD_WORLD
from mud.utils import get_target_obj, get_recorded_history_for_event, prepare_action_changes

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
        'Access-Control-Allow-Headers': 'access-control-allow-origin, content-type',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, PATCH, OPTIONS',
        'Access-Control-Allow-Credentials': "true"
    }
    if 'Origin' in request.headers:
        headers['Access-Control-Allow-Origin'] = request.headers['Origin']
    for header in extra_headers.keys():
        headers[header] = extra_headers[header]
    return headers

def _get_default_options_response(request):
    return jsonify({}), 200, _get_headers()

def _base64_to_png_response(image_as_base64_string: str, filename="image.png"):
  """
  From a string representing a base64 image, convert it to a png
  and wrap it in a flask Response"""
  image_data = image_as_base64_string.replace('data:image/png;base64,', '')
  decoded_image = base64.b64decode(image_data)
  response_headers = {
      'Content-Type': 'image/png',
      'Content-Disposition': f'attachment; filename={filename}'
  }
  return Response(decoded_image, headers=response_headers)

@app.route("/images/<image_path>")
def image_uploaded(image_path):
    return send_file(f"./images/{image_path}", mimetype='image/png'), 200, _get_headers()

@app.route("/register/", methods=["POST"])
def register():
    jsonld = copy.deepcopy(request.get_json())
    if "foaf:username" not in jsonld:
        return "foaf:username is required", 400, _get_headers()
    if len(list(db.users.find({"foaf:username": jsonld["foaf:username"]}))) > 0:
        return "user already exists", 409, _get_headers()
    
    if "_id" in jsonld:
        jsonld.pop("_id")

    if "@type" not in jsonld or len(jsonld["@type"]) == 0:
        jsonld["@type"] = "foaf:Person"

    if "@id" not in jsonld or len(jsonld["@id"]) == 0:
        jsonld["@id"] = f"{site_url}/users/{str(jsonld['foaf:username'])}/"
    
    if "mudacct:Account" not in jsonld:
        jsonld["mudacct:Account"] = {
            "@id": f"{site_url}/users/{str(jsonld['foaf:username'])}/account/",
            "@type": MUD_ACCT.Account,
            "mudacct:characterList": f"{site_url}/characters/by/{str(jsonld['foaf:username'])}/"
        }

    db.users.find_one_and_replace(
        {"foaf:username": jsonld["foaf:username"]},
        jsonld,
        upsert=True
    )

@app.route("/characters/by/<creator>/", methods=['GET'])
def characters_by_user(creator):
    characters = list(db.characters.find({"dcterms:creator": creator}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/characters/<character_id>/", methods=['GET'])
def character_detail(character_id):
    c = db.characters.find_one({"@id": f"{site_url}/characters/{character_id}/"})
    if c is None:
        return "character with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(c))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/characters/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def characters():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_CHAR.Character

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/characters/{str(uuid.uuid4())}/"

        # process image
        if "foaf:depiction" in jsonld and len(jsonld["foaf:depiction"]) > 0:
            # don't try to read images from own site
            if not urlparse(jsonld["foaf:depiction"]).netloc == urlparse(site_url).netloc:
                fd = urlopen(jsonld["foaf:depiction"])
                image_file = io.BytesIO(fd.read())
                im = Image.open(image_file)
                im.thumbnail((512, 512), Image.Resampling.LANCZOS)
                filename = str(uuid.uuid4()) + ".png"
                im.save(f'./images/{filename}')
                jsonld["foaf:depiction"] = site_url + "/images/" + filename

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

        db.characters.find_one_and_delete({"@id": jsonld["@id"]})

        return "", 204, _get_headers()

    characters = list(db.characters.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/cards/<card_id>/", methods=['GET'])
def card_detail(card_id):
    c = db.cards.find_one({"@id": f"{site_url}/cards/{card_id}/"})
    if c is None:
        return "card with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(c))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/cards/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def cards():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_CHAR.Character

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/cards/{str(uuid.uuid4())}/"
        
        # process image
        if "foaf:depiction" in jsonld and len(jsonld["foaf:depiction"]) > 0:
            # don't try to read images from own site
            if not urlparse(jsonld["foaf:depiction"]).netloc == urlparse(site_url).netloc:
                fd = urlopen(jsonld["foaf:depiction"])
                image_file = io.BytesIO(fd.read())
                im = Image.open(image_file)
                im.thumbnail((512, 512), Image.Resampling.LANCZOS)
                filename = str(uuid.uuid4()) + ".png"
                im.save(f'./images/{filename}')
                jsonld["foaf:depiction"] = site_url + "/images/" + filename
        
        # TODO: workaround, fix client-side
        if "mudcard:hasAvailableInstantActions" in jsonld:
            for i in range(len(jsonld["mudcard:hasAvailableInstantActions"])):
                if "uri" in jsonld["mudcard:hasAvailableInstantActions"][i]:
                    jsonld["mudcard:hasAvailableInstantActions"][i]["@id"] = jsonld["mudcard:hasAvailableInstantActions"][i].pop("uri")
                
        # cap maximum HP to 30
        if "mudcombat:hasHealthPoints" in jsonld:
            if "mudcombat:maximumP" not in jsonld["mudcombat:hasHealthPoints"]:
                jsonld["mudcombat:hasHealthPoints"]["mudcombat:maximumP"] = 10
            
            jsonld["mudcombat:hasHealthPoints"]["mudcombat:maximumP"] = min(30, int(jsonld["mudcombat:hasHealthPoints"]["mudcombat:maximumP"]))
        
        # clean resistance value - make sure it's a percentage
        if "mudcombat:hasResistances" in jsonld:
            for i in range(jsonld["mudcombat:hasResistances"]):
                resistance = jsonld["mudcombat:hasResistances"][i]
                if "mudcombat:resistanceValue" not in resistance:
                    jsonld["mudcombat:hasResistances"][i]["mudcombat:resistanceValue"] = 0.5
                elif resistance["mudcombat:resistanceValue"] > 1:
                    res_value = resistance["mudcombat:resistanceValue"] * 0.1

                    while res_value > 1:
                        res_value = res_value * 0.1

                    jsonld["mudcombat:hasResistances"][i]["mudcombat:resistanceValue"] = res_value

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
        
        val = db.cards.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, _get_headers()

        return "", 204, _get_headers()

    cards = list(db.cards.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(cards))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/worlds/templates/<world_id>/", methods=['GET'])
def world_templates_detail(world_id):
    w = db.world_templates.find_one({"@id": f"{site_url}/worlds/templates/{world_id}/"})
    if w is None:
        return "world with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(w))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/worlds/templates/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def world_templates():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_WORLD.Region

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/worlds/templates/{str(uuid.uuid4())}/"

        db.world_templates.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, _get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.world_templates.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, _get_headers()

        return "", 204, _get_headers()

    world = list(db.world_templates.find({"@type": MUD_WORLD.Region}))
    return jsonify(json.loads(json_util.dumps(world))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/worlds/<world_id>/", methods=['GET'])
def world_detail(world_id):
    w = db.worlds.find_one({"@id": f"{site_url}/worlds/{world_id}/"})
    if w is None:
        return "world with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(w))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/worlds/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def worlds():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_WORLD.Region

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/worlds/{str(uuid.uuid4())}/"

        db.worlds.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, _get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.worlds.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, _get_headers()

        return "", 204, _get_headers()

    world = list(db.worlds.find({"@type": MUD_WORLD.Region}))
    return jsonify(json.loads(json_util.dumps(world))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/ud/stories/<story_id>/", methods=['GET'])
def story_detail(story_id):
    s = db.stories.find_one({"@id": f"{site_url}/ud/stories/{story_id}/"})
    if s is None:
        return "story with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(s))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/ud/stories/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def stories():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_DIALOGUE.Interaction

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/ud/stories/{str(uuid.uuid4())}/"

        db.stories.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, _get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.stories.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, _get_headers()

        return "", 204, _get_headers()

    stories = list(db.stories.find({"@type": MUD_DIALOGUE.Interaction}))
    return jsonify(json.loads(json_util.dumps(stories))), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/ud/generateContext/", methods=['POST', 'OPTIONS'])
def generate_context():
    """
    Takes a given dialogue Interaction and world state and makes the appropriate bindings/generates the appropriate content according to the Interaction bindings
    Returns the result
    """
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    def fail_unable_to_find_binding(shape):
        shape_name = shape['@id'] if "@id" in shape else shape["n:fn"] if "n:fn" in shape else ""
        return f"Could not make a binding to shape {shape_name} with given world data", 404, _get_headers()

    def can_bind_candidate_to_shape(candidate_obj, shape):
        world_graph = Graph()
        world_graph.parse(data=json.dumps(candidate_obj), format='json-ld')
        shapes = Graph()
        shapes.parse(data=json.dumps(shape), format='json-ld')

        validate_result, report, message = validate(world_graph, shacl_graph=shapes, inference="none")
        #syslog.syslog(str(candidate_obj["@id"]) + " passed on shape (" + str(validate_result) + ")")
        #syslog.syslog(str(world_graph.serialize()))
        #syslog.syslog("\n\n")
        #syslog.syslog(str(shapes.serialize()))
        return validate_result
    
    def get_candidates_from_world_data_for_binding(world_data, binding, shape):
        """
        Iterates over the world_data candidates
        :return: a list of all candidate indecies who meet the conditions of the binding/shape
        """
        
        valid_choices = []
        for candidate_idx in range(len(world_data)):
            candidate_obj = world_data[candidate_idx]

            #if "muddialogue:bindingToType" in binding and "@type" in candidate_obj and binding["muddialogue:bindingToType"] != candidate_obj["@type"]:
            #    continue
            
            if can_bind_candidate_to_shape(candidate_obj, shape):
                valid_choices.append(candidate_idx)
        
        return valid_choices
    
    jsonld = request.get_json()

    if "givenInteraction" not in jsonld or "givenWorld" not in jsonld:
        return "'givenInteraction' and 'givenWorld' are required parameters for this function", 400, _get_headers()
    
    interaction_data = jsonld["givenInteraction"]
    # NOTE: for now the world data is just a list of candidate characters
    world_data = jsonld["givenWorld"]
    # a dictionary which will contain all binding matches and information about them
    binding_candidates_dict = {}

    # iterate each binding and create a map of candidates from the world data which could be applied to it
    for i in range(len(interaction_data["muddialogue:hasBindings"])):
        binding = interaction_data["muddialogue:hasBindings"][i]
        shape = binding["muddialogue:bindingMadeToShape"] if "muddialogue:bindingMadeToShape" in binding else {}

        # TODO: a better way to tell if I need to fetch it
        if len(shape.keys()) == 1 and "@id" in shape:
            # TODO: read remote shape
            return "Remote shapes are not currently supported, please serialize all binding shapes fully into JSON-LD", 400, _get_headers()
        
        valid_candidates = get_candidates_from_world_data_for_binding(world_data, binding, shape)

        # TODO: instruction for generating a candidate if none avaliable
        if len(valid_candidates) == 0:
            print("no valid candidates available for shape " + str(shape))
            syslog.syslog("no valid candidates available for shape " + str(shape))
            return fail_unable_to_find_binding(shape)
        
        binding_candidates_dict[str(i)] = {
            "valid_candidates": valid_candidates,
            "unique": "muddialogue:bindingIsUnique" in binding and binding["muddialogue:bindingIsUnique"]
        }
    
    # for each binding, select the candidates which will be applied to it
    unique_bindings = [binding_candidates_dict[b] for b in binding_candidates_dict.keys() if binding_candidates_dict[b]["unique"]]
    candidates_in_unique_bindings = set()
    for b in unique_bindings:
        candidates_in_unique_bindings = candidates_in_unique_bindings.union(set([c for c in b["valid_candidates"]]))
    
    print(str(binding_candidates_dict))
    commit_selection = [] # array containing indecies that can't be selected again
    
    def non_committed_candidates(candidates):
        return [c for c in candidates if c not in commit_selection]    

    for binding_idx in binding_candidates_dict.keys():
        binding = binding_candidates_dict[binding_idx]
        # if this binding only has one choice, choose it
        if len(binding["valid_candidates"]) == 1:
            interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] = world_data[binding["valid_candidates"][0]]
            if binding["unique"]:
                commit_selection.append(binding["valid_candidates"][0])
            continue

        # if this binding isn't unique, if there is a candidate which doesn't exist in a unique_binding then select it
        if not binding["unique"]:
            for candidate in non_committed_candidates(binding["valid_candidates"]):
                if candidate not in candidates_in_unique_bindings:
                    interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] = world_data[candidate]
                    break
            if "muddialogue:boundTo" in interaction_data["muddialogue:hasBindings"][binding_idx] and \
                interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] is not None:
                continue
            
            # if those unique bindings lack options which are outside of this binding, it's impossible to succeed
            interest_candidates = set(non_committed_candidates(candidates_in_unique_bindings)).difference(set(non_committed_candidates(binding["valid_candidates"])))
            if len(interest_candiates) == 0:
                return fail_unable_to_find_binding(shape)

            # NOTE: this isn't fool-proof, just a good choice
            # select from a unique binding which has other options one of my overlapping candidates
            for u in unique_bindings:
                diff_set = set(non_committed_candidates(u["valid_candidates"])).difference(set(non_committed_candidates(binding["valid_candidates"])))
                if len(diff_set) > 0:
                    selected_idx = list(set(non_committed_candidates(u["valid_candidates"])).difference(diff_set))[0]
                    interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] = world_data[selected_idx]
                    if binding["unique"]:
                        commit_selection.append(selected_idx)
                    break
        # this binding is unique
        else:
            # if there is a candidate which doesn't exist in another binding, select it
            candidate_set = set(non_committed_candidates(binding["valid_candidates"]))
            for b_idx in binding_candidates_dict.keys():
                b = binding_candidates_dict[b_idx]
                if b_idx == binding_idx:
                    continue
                candidate_set = candidate_set.difference(set(b["valid_candidates"]))
            if len(candidate_set) > 0:
                selected_idx = list(candidate_set)[0]
                interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] = world_data[selected_idx]
                commit_selection.append(selected_idx)
                continue
            
            # NOTE: this isn't fool-proof, just a good choice
            # TODO: select a candidate which exists only in bindings with the most options
            #for candidate in non_committed_candidates(binding["valid_candidates"]):
            #    pass
            selected_idx = non_committed_candidates(binding["valid_candidates"])[0]
            interaction_data["muddialogue:hasBindings"][int(binding_idx)]["muddialogue:boundTo"] = world_data[selected_idx]
            commit_selection.append(selected_idx)

    return jsonify({
        "givenInteraction": interaction_data,
        "givenWorld": world_data
    }), 200, _get_headers({'Content-Type': 'application/ld+json'})

@app.route("/content/sceneDescription/", methods=["POST", "OPTIONS"])
def scene_description():
    if request.method == 'OPTIONS':
        return _get_default_options_response(request)
    
    return "Scene Description endpoint is TODO"

'''
Routes for supporting complex behaviour in cards
'''

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

    return jsonify(result), 200, _get_headers({'Content-Type': 'application/ld+json'})
