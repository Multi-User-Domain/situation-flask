import copy
from flask import Blueprint, request
from mud.vocab import MUD_ACCT
from view_utils import get_headers
from config import db, site_url


users_blueprint = Blueprint('users', __name__)


@users_blueprint.route("/register/", methods=["POST"])
def register():
    jsonld = copy.deepcopy(request.get_json())
    if "foaf:username" not in jsonld:
        return "foaf:username is required", 400, get_headers()
    if len(list(db.users.find({"foaf:username": jsonld["foaf:username"]}))) > 0:
        return "user already exists", 409, get_headers()
    
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
