import uuid

#
#   A collection of utilities for working with MUD formats
#

def get_target_obj(world_data, action_data):
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


def get_recorded_history_for_event(event_text):
    return {
        "@id": "_:RecordedHistory_" + str(uuid.uuid4()),
        "@type": "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/games/twt2023.ttl#RecordedHistory",
        "n:hasNote": event_text
    }


def prepare_action_changes(action_data, deletes=[], inserts=[]):
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
