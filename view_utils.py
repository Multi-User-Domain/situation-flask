from flask import request, Response, jsonify


def get_headers(extra_headers={}):
    """Appends extra_headers to the default headers of the app"""
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


def get_default_options_response(request):
    return jsonify({}), 200, get_headers()
