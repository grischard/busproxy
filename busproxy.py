#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Params are:
# maxFeatures=10
# lang=fr
# layers=arrets_bus
# scale=425196
# bbox=76450,75525,77950,77025
# cb=callback

# curl 'http://map.geoportail.lu/bodfeature/search?layers=arrets_bus&bbox=77529,72364,78539,73374' -H 'Referer: http://localhost'

from flask import Flask, request, Response
from pyproj import Proj, transform
import requests
import json
import os
import validate_jsonp

app = Flask(__name__)

LUREF = Proj("+init=EPSG:2169")
WGS84 = Proj(proj='latlong', datum='WGS84')


def get_features(bbox):
    layer = request.form.get('layer', 'arrets_bus')  # default layer is arrets_bus
    limit = request.form.get('limit', '100')         # default limit is 100
    debug = request.form.get('debug', False)         # default debug is False
    callback = request.form.get('callback', None)    # default callback is None
    my_referer = 'http://localhost'

    url = 'http://map.geoportail.lu/bodfeature/search?layers={0}&bbox={1},{2},{3},{4}&maxFeatures={5}'.format(layer, bbox[0], bbox[1], bbox[2], bbox[3], limit)
    app.logger.debug('URL: %s', url)

    headers = {'Referer': my_referer}
    r = requests.get(url, headers=headers)
    myjson = r.json()
    if myjson['type'] == 'FeatureCollection':
        for feature in myjson['features']:
            pos = transform(LUREF, WGS84, feature['geometry']['coordinates'][0], feature['geometry']['coordinates'][1])
            feature['geometry']['coordinates'] = ["{0:.6f}".format(pos[1]), "{0:.6f}".format(pos[0])]
    if debug:
        myjson = json.dumps(myjson, indent=4, sort_keys=True, ensure_ascii=False, separators=(',', ': ')).encode('utf8')
    else:
        myjson = json.dumps(myjson).encode('utf8')
    if callback:
        if validate_jsonp.is_valid_jsonp_callback_value(callback):
            myjson = callback + '(' + myjson + ');'
        else:
            return 'Callback must be valid Javascript identifier as defined in the ECMAScript specification'
    return myjson


@app.route('/')
def hello():
    return 'Try /around/49.61/6.12 , perhaps with ?radius=100 and &callback=foo . Data scraped from Verkéiersverbond, Geoportail.'


@app.route('/around/<float:lon>/<float:lat>')
def around(lon, lat):
    '''Given a lat, lon, return points within the square that contains <radius> circle. Default radius is 1000.'''
    radius = request.form.get('radius', 1000)  # default radius 1000
    pos = transform(WGS84, LUREF, lat, lon)
    bbox = [round(pos[0]-radius), round(pos[1]-radius), round(pos[0]+radius), round(pos[1]+radius)]
    # show the bus stops within (radius) of that point
    results = get_features(bbox)

    resp = Response(response=results, status=200, mimetype="application/json")
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if port == 5000:
        app.debug = True
    app.run(host='0.0.0.0', port=port)
