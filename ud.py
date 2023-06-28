import copy
import json
import io
import uuid
import syslog
from rdflib import Graph
from pyshacl import validate
from bson import json_util
from flask import Blueprint, request, jsonify
from mud.vocab import MUD_DIALOGUE
from view_utils import get_headers, get_default_options_response
from config import db, site_url


ud_blueprint = Blueprint('ud', __name__)


@ud_blueprint.route("/stories/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def stories():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
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

        return jsonify(jsonld), 201, get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.stories.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, get_headers()

        return "", 204, get_headers()

    stories = list(db.stories.find({"@type": MUD_DIALOGUE.Interaction}))
    return jsonify(json.loads(json_util.dumps(stories))), 200, get_headers({'Content-Type': 'application/ld+json'})


@ud_blueprint.route("/stories/<story_id>/", methods=['GET'])
def story_detail(story_id):
    s = db.stories.find_one({"@id": f"{site_url}/ud/stories/{story_id}/"})
    if s is None:
        return "story with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(s))), 200, get_headers({'Content-Type': 'application/ld+json'})


@ud_blueprint.route("/generateContext/", methods=['POST', 'OPTIONS'])
def generate_context():
    """
    Takes a given dialogue Interaction and world state and makes the appropriate bindings/generates the appropriate content according to the Interaction bindings
    Returns the result
    """
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    def fail_unable_to_find_binding(shape):
        shape_name = shape['@id'] if "@id" in shape else shape["n:fn"] if "n:fn" in shape else ""
        return f"Could not make a binding to shape {shape_name} with given world data", 404, get_headers()

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
        return "'givenInteraction' and 'givenWorld' are required parameters for this function", 400, get_headers()
    
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
            return "Remote shapes are not currently supported, please serialize all binding shapes fully into JSON-LD", 400, get_headers()
        
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
    }), 200, get_headers({'Content-Type': 'application/ld+json'})
