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
import re

app = Flask(__name__)

LUREF = Proj("+init=EPSG:2169")
WGS84 = Proj(proj='latlong', datum='WGS84')

bboxregex = re.compile('([-+]?[0-9]*\.?[0-9]+,){3}([-+]?[0-9]*\.?[0-9]+)')  # four comma-separated ints or floats.

def get_features(bbox):
    layer = request.args.get('layer', default='arrets_bus')    # default layer is arrets_bus
    limit = request.args.get('limit', default=9999, type=int)  # default limit is 9999
    debug = request.args.get('debug', False)                   # default debug is False
    callback = request.args.get('callback', None)              # default callback is None

    url = 'http://map.geoportail.lu/bodfeature/search?layers={0}&bbox={1},{2},{3},{4}&maxFeatures={5}'.format(layer, bbox[0], bbox[1], bbox[2], bbox[3], limit)
    my_referer = 'http://localhost'

    app.logger.debug('URL: %s', url)

    headers = {'Referer': my_referer, 'User-Agent': 'Salut vun busproxy.herokuapp.com'}
    r = requests.get(url, headers=headers)
    myjson = r.json()
    if myjson['type'] == 'FeatureCollection':
        for feature in myjson['features']:
            pos = transform(LUREF, WGS84, feature['geometry']['coordinates'][0], feature['geometry']['coordinates'][1])
            feature['geometry']['coordinates'] = ["{0:.6f}".format(pos[0]), "{0:.6f}".format(pos[1])]
            if not debug:
                del feature['properties']['html']
            feature['properties']['mobiliteitid'] = feature['id']
            del feature['id']
    if debug:
        myjson = json.dumps(myjson, indent=4, sort_keys=True, ensure_ascii=False, separators=(',', ': '))
    else:
        myjson = json.dumps(myjson).encode('utf8')
    if callback:
        if validate_jsonp.is_valid_jsonp_callback_value(callback):
            myjson = callback + '(' + myjson + ');'
        else:
            return 'Callback must be valid Javascript identifier as defined in the ECMAScript specification'
    return myjson.encode('utf8')


@app.route('/')
def hello():
    return """
              <!doctype html>
              <html>
              <head>
                  <title>Bus stop json proxy</title>
              </head>
              <body>
              <h2>Bus proxy</h2>
              <p>Translates between wgs84 and luref, and sends http://localhost as a referer. Gets you Luxembourg bus stops in json.</p>
              <p>Try <a href="/around/49.61/6.12">/around/49.61/6.12</a> or <a href="/bbox/6.11,49.59,6.15,49.60">/bbox/6.11,49.59,6.15,49.60</a> (WSEN)</p>
              <h4>Optional GET parameters</h4>
              <ul>
                  <li><a href="/around/49.61/6.12?radius=100"><b>radius</b></a>, default <b>100</b>. App will return points within the square that contains [radius] circle. Only for /around.</li>
                  <li><a href="/around/49.61/6.12?callback=mycallback"><b>callback</b></a>, default <b>None</b>. See <a href="https://en.wikipedia.org/wiki/JSONP">JSONP</a>.</li>
                  <li><a href="/around/49.61/6.12?debug=True"><b>debug</b></a>, default <b>False</b>. Pretty-print json, include all the garbage from the original json.</li>
              </ul>
              <h4>What do I do with this?</h4>
              <ul>
                  <li>The output is valid geojson, which you can easily <a href="http://leafletjs.com/examples/geojson.html">display on a map</a></li>
                  <li>With the bus ID, you can get a <a href="http://travelplanner.mobiliteit.lu/hafas/cdt/help.exe/dn?tpl=infobox&iblayout=1&ibname=xss&ibextid=200405020&ibinit=box_2">live departures/arrivals board</a> and even <a href="http://travelplanner.mobiliteit.lu/hafas/cdt/stboard.exe/dn?L=vs_stb&input=200405020&boardType=dep&time=now&selectDate=today&start=yes&requestType=0&maxJourneys=20">json</a>. Using https://getcontents.herokuapp.com/?url=http%3A%2F%2Ftravelplanner.mobiliteit.lu etc. can make this easier to integrate.
              <p>Data <a href="https://en.wikipedia.org/wiki/Web_scraping#Legal_issues">scraped without permission</a> from Verkéiersverbond, Geoportail. <emph>Mat ♥ codéiert.</emph></p>
              </body>
              </html>
              """


@app.route('/around/<float:lon>/<float:lat>')
def around(lon, lat):
    '''Given a lat, lon, return points within the square that contains <radius> circle. Default radius is 100.'''
    radius = request.form.get('radius', 1000)  # default radius 1000
    pos = transform(WGS84, LUREF, lat, lon)
    bbox = [round(pos[0]-radius), round(pos[1]-radius), round(pos[0]+radius), round(pos[1]+radius)]
    # show the bus stops within (radius) of that point
    return send_json(get_features(bbox))

@app.route('/bbox/<mybbox>')
def bbox(mybbox):
    '''Given a bbox, return points within it. GeoJSON standard for bbox is WSEN.'''
    # 6.11,49.59,6.15,49.60
    # W    S     E    N
    # if
    # pos_bottomleft= transform(WGS84, LUREF, lat, lon)
    if bboxregex.match(mybbox):
        mybbox = mybbox.split(",")
        pos_bottomleft = transform(WGS84, LUREF, mybbox[0], mybbox[1])
        pos_topright = transform(WGS84, LUREF, mybbox[2], mybbox[3])
        return send_json(get_features([pos_bottomleft[0], pos_bottomleft[1], pos_topright[0], pos_topright[1]]))
    else:
        return "BBOX not understood. Format must be like 6.11,49.59,6.15,49.60, order is WSEN."

def send_json(myjson):
    resp = Response(response=myjson, status=200, mimetype="application/json")
    resp.headers.add('Access-Control-Allow-Origin', '*')
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if port == 5000:
        app.debug = True
    app.run(host='0.0.0.0', port=port)
