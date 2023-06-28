import copy
import json
import io
import uuid
from urllib.parse import urlparse
from urllib.request import urlopen
from bson import json_util
from PIL import Image
from flask import Blueprint, request, jsonify
from mud.vocab import MUD_CHAR
from view_utils import get_headers, get_default_options_response
from config import db, site_url

characters_blueprint = Blueprint('characters', __name__)

'''
@characters_blueprint.route("/character-templates/", methods=['GET'])
def character_templates():
    characters = list(db.character_templates.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, {'Content-Type': 'application/ld+json'}
'''

@characters_blueprint.route("/by/<creator>/", methods=['GET'])
def characters_by_user(creator):
    characters = list(db.characters.find({"dcterms:creator": creator}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, get_headers({'Content-Type': 'application/ld+json'})

@characters_blueprint.route("/<character_id>/", methods=['GET'])
def character_detail(character_id):
    c = db.characters.find_one({"@id": f"{site_url}/characters/{character_id}/"})
    if c is None:
        return "character with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(c))), 200, get_headers({'Content-Type': 'application/ld+json'})

@characters_blueprint.route("/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def characters():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
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

        return jsonify(jsonld), 201, get_headers({'Content-Type': 'application/ld+json'})
    
    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400

        db.characters.find_one_and_delete({"@id": jsonld["@id"]})

        return "", 204, get_headers()

    characters = list(db.characters.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(characters))), 200, get_headers({'Content-Type': 'application/ld+json'})
