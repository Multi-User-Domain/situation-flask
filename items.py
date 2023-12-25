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

items_blueprint = Blueprint('items', __name__)


@items_blueprint.route("/<item_id>/", methods=['GET'])
def item_detail(item_id):
    item = db.items.find_one({"urlid": f"{site_url}/items/{item_id}/"})
    if item is None:
        return "item with this urlid not found", 404
    return jsonify(json.loads(json_util.dumps(item))), 200, get_headers({'Content-Type': 'application/json'})

@items_blueprint.route("/", methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def items():
    if request.method == 'OPTIONS':
        return get_default_options_response(request)
    
    if request.method == 'POST':
        json_data = copy.deepcopy(request.get_json())

        if "_id" in json_data:
            json_data.pop("_id")

        if "type" not in json_data or len(json_data["type"]) == 0:
            json_data["type"] = "item"

        if "urlid" not in json_data or len(json_data["urlid"]) == 0:
            json_data["urlid"] = f"{site_url}/items/{str(uuid.uuid4())}/"

        # TODO: process spritesheet
        """
        if "foaf:depiction" in json_data and len(json_data["foaf:depiction"]) > 0:
            # don't try to read images from own site
            if not urlparse(json_data["foaf:depiction"]).netloc == urlparse(site_url).netloc:
                fd = urlopen(json_data["foaf:depiction"])
                image_file = io.BytesIO(fd.read())
                im = Image.open(image_file)
                im.thumbnail((512, 512), Image.Resampling.LANCZOS)
                filename = str(uuid.uuid4()) + ".png"
                im.save(f'./images/{filename}')
                json_data["foaf:depiction"] = site_url + "/images/" + filename
        """

        db.items.find_one_and_replace(
            {"urlid": json_data["urlid"]},
            json_data,
            upsert=True
        )

        return jsonify(json_data), 201, get_headers({'Content-Type': 'application/json'})
    
    if request.method == 'DELETE':
        json_data = request.get_json()

        if "urlid" not in json_data:
            return "urlid key is required for DELETE", 400

        db.items.find_one_and_delete({"urlid": json_data["urlid"]})

        return "", 204, get_headers()

    items = list(db.items.find({"type": "item"}))
    return jsonify(json.loads(json_util.dumps(items))), 200, get_headers({'Content-Type': 'application/json'})
