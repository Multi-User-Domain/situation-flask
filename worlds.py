import copy
import json
import uuid
from bson import json_util
from flask import Blueprint, request, jsonify
from mud.vocab import MUD_WORLD
from view_utils import get_headers, get_default_options_response
from config import db, site_url


worlds_blueprint = Blueprint('worlds', __name__)


@worlds_blueprint.route("/templates/<world_id>/", methods=['GET'])
def world_templates_detail(world_id):
    w = db.world_templates.find_one({"@id": f"{site_url}/worlds/templates/{world_id}/"})
    if w is None:
        return "world with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(w))), 200, get_headers({'Content-Type': 'application/ld+json'})

@worlds_blueprint.route("/templates/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def world_templates():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
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

        return jsonify(jsonld), 201, get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.world_templates.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, get_headers()

        return "", 204, get_headers()

    world = list(db.world_templates.find({"@type": MUD_WORLD.Region}))
    return jsonify(json.loads(json_util.dumps(world))), 200, get_headers({'Content-Type': 'application/ld+json'})

@worlds_blueprint.route("/<world_id>/", methods=['GET'])
def world_detail(world_id):
    w = db.worlds.find_one({"@id": f"{site_url}/worlds/{world_id}/"})
    if w is None:
        return "world with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(w))), 200, get_headers({'Content-Type': 'application/ld+json'})


def generate_tile_map_for_world(jsonld):
    assert "mudworld:hasRegions" in jsonld, "Require a world with regions in order to generate tilemap"

    def generate_empty_tilemap(region):
        # don't replace existing tilemap
        if "mudworld:hasTileMap" in region:
            return region

        # read the tile map size parameters from the object, or store defaults if this information is missing
        tile_map_x_size = 90
        tile_map_y_size = 90
        tile_map_z_size = 0

        if "mudworld:hasSize" in region:
            if "x" in region["mudworld:hasSize"]:
                tile_map_x_size = region["mudworld:hasSize"]["x"]
            if "y" in region["mudworld:hasSize"]:
                tile_map_y_size = region["mudworld:hasSize"]["y"]
            if "z" in region["mudworld:hasSize"]:
                tile_map_z_size = region["mudworld:hasSize"]["z"]
        else:
            region["mudworld:hasSize"] = {
                "@type":"https://w3id.org/mdo/structure/CoordinateVector","x": tile_map_x_size, "y": tile_map_y_size,"z": tile_map_z_size
            }

        # generate the size of the tile map
        # TODO: support 3D maps
        region['mudworld:hasTileMap'] = []
        for x in range(tile_map_x_size):
            region['mudworld:hasTileMap'] = [[-1] * tile_map_y_size] * tile_map_x_size
        
        # TODO: procedural generation from instructions. Place objects which exist in the region etc
        return region
    
    def generate_tile_map_for_leaf_regions(region):
        if "mudworld:hasRegions" in region:
            for i in range(len(region["mudworld:hasRegions"])):
                region["mudworld:hasRegions"][i] = generate_tile_map_for_leaf_regions(region["mudworld:hasRegions"][i])
        else:
            region = generate_empty_tilemap(region)
        
        return region

    # generate tile maps for all leaf regions
    jsonld = generate_tile_map_for_leaf_regions(jsonld)
    
    return jsonld


@worlds_blueprint.route("/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def worlds():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    if request.method == 'POST':
        jsonld = copy.deepcopy(request.get_json())

        if "_id" in jsonld:
            jsonld.pop("_id")

        if "@type" not in jsonld or len(jsonld["@type"]) == 0:
            jsonld["@type"] = MUD_WORLD.Region

        if "@id" not in jsonld or len(jsonld["@id"]) == 0:
            jsonld["@id"] = f"{site_url}/worlds/{str(uuid.uuid4())}/"
        
        if "mudworld:hasRegions" in jsonld:
            jsonld = generate_tile_map_for_world(jsonld)

        db.worlds.find_one_and_replace(
            {"@id": jsonld["@id"]},
            jsonld,
            upsert=True
        )

        return jsonify(jsonld), 201, get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.worlds.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, get_headers()

        return "", 204, get_headers()

    world = list(db.worlds.find({"@type": MUD_WORLD.Region}))
    return jsonify(json.loads(json_util.dumps(world))), 200, get_headers({'Content-Type': 'application/ld+json'})
