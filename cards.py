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


cards_blueprint = Blueprint('cards', __name__)


@cards_blueprint.route("/<card_id>/", methods=['GET'])
def card_detail(card_id):
    c = db.cards.find_one({"@id": f"{site_url}/cards/{card_id}/"})
    if c is None:
        return "card with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(c))), 200, get_headers({'Content-Type': 'application/ld+json'})

@cards_blueprint.route("/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def cards():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
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

        return jsonify(jsonld), 201, get_headers({'Content-Type': 'application/ld+json'})

    if request.method == 'DELETE':
        jsonld = request.get_json()

        if "@id" not in jsonld:
            return "@id key is required for DELETE", 400
        
        val = db.cards.find_one_and_delete({"@id": jsonld["@id"]})

        if val is None:
            return "", 404, get_headers()

        return "", 204, get_headers()

    cards = list(db.cards.find({"@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"}))
    return jsonify(json.loads(json_util.dumps(cards))), 200, get_headers({'Content-Type': 'application/ld+json'})
