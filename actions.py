import copy
import json
import io
import uuid
from bson import json_util
from flask import Blueprint, request, jsonify
from view_utils import get_headers, get_default_options_response
from config import db, site_url

actions_blueprint = Blueprint('actions', __name__)


@actions_blueprint.route("/<action_id>/", methods=['GET'])
def action_detail(action_id):
    action = db.actions.find_one({"urlid": f"{site_url}/actions/{action_id}/"})
    if action is None:
        return "action with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(action))), 200, get_headers({'Content-Type': 'application/json'})

@actions_blueprint.route("/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def actions():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    if request.method == 'POST':
        json_data = copy.deepcopy(request.get_json())

        if "_id" in json_data:
            json_data.pop("_id")

        if "type" not in json_data or len(json_data["type"]) == 0:
            json_data["type"] = "action"

        if "urlid" not in json_data or len(json_data["urlid"]) == 0:
            json_data["urlid"] = f"{site_url}/actions/{str(uuid.uuid4())}/"

        db.actions.find_one_and_replace(
            {"urlid": json_data["urlid"]},
            json_data,
            upsert=True
        )

        return jsonify(json_data), 201, get_headers({'Content-Type': 'application/json'})
    
    if request.method == 'DELETE':
        json_data = request.get_json()

        if "urlid" not in json_data:
            return "urlid key is required for DELETE", 400

        db.actions.find_one_and_delete({"urlid": json_data["urlid"]})

        return "", 204, get_headers()

    actions = list(db.actions.find({"type": "action"}))
    return jsonify(json.loads(json_util.dumps(actions))), 200, get_headers({'Content-Type': 'application/json'})


@actions_blueprint.route("/recipes/<recipe_id>/", methods=['GET'])
def recipe_detail(recipe_id):
    recipe = db.recipes.find_one({"urlid": f"{site_url}/recipes/{recipe_id}/"})
    if recipe is None:
        return "recipe with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(recipe))), 200, get_headers({'Content-Type': 'application/json'})


@actions_blueprint.route("/recipes/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def recipes():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    if request.method == 'POST':
        json_data = copy.deepcopy(request.get_json())

        if "_id" in json_data:
            json_data.pop("_id")

        if "type" not in json_data or len(json_data["type"]) == 0:
            json_data["type"] = "recipe"

        if "urlid" not in json_data or len(json_data["urlid"]) == 0:
            json_data["urlid"] = f"{site_url}/recipes/{str(uuid.uuid4())}/"

        db.recipes.find_one_and_replace(
            {"urlid": json_data["urlid"]},
            json_data,
            upsert=True
        )

        return jsonify(json_data), 201, get_headers({'Content-Type': 'application/json'})
    
    if request.method == 'DELETE':
        json_data = request.get_json()

        if "urlid" not in json_data:
            return "urlid key is required for DELETE", 400

        db.recipes.find_one_and_delete({"urlid": json_data["urlid"]})

        return "", 204, get_headers()

    recipes = list(db.recipes.find({"type": "recipe"}))
    return jsonify(json.loads(json_util.dumps(recipes))), 200, get_headers({'Content-Type': 'application/json'})
