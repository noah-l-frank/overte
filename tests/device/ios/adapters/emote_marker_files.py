"""Owned marker-only Script bytes, staged through the existing private file API.

Loading remains ordinary Script manager/picker input. File delivery supplies no
rendered marker, animation, pose, peer or execution verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import re
import secrets
from adapters.native_feature_observation import exact,need
from adapters.native_script_files import OwnedScriptFiles,NAMES
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from feature_journeys.navigation_scene import resource_root

VERSION=1


def originals(run,fixture_url,ticket,nonce):
    identifier(run);identifier(ticket);identifier(nonce);resource_root(fixture_url,run)
    # The only product mutation is one local Web marker. Never write MyAvatar,
    # navigation, animations, menus or a requested feature result from this code.
    url=fixture_url+'tickets/'+ticket+'/graphics-marker.v1.html'
    body='''"use strict";
(function () {
    var companion = Script.require("./companion.js");
    var marker = Entities.addEntity({
        type: "Web", name: NAME,
        userData: DATA,
        position: Vec3.sum(MyAvatar.position,
            Vec3.multiplyQbyV(MyAvatar.orientation, {x: 0, y: 1.6, z: -3})),
        rotation: MyAvatar.orientation,
        dimensions: {x: 1.6, y: 0.4, z: 0.01},
        sourceUrl: URL, visible: true, collisionless: true, dpi: 100
    }, "local");
    Script.scriptEnding.connect(function () {
        if (marker) { Entities.deleteEntity(marker); }
    });
}());
'''
    body=body.replace('NAME',json.dumps('e2e-'+run+'-script')).replace('DATA',json.dumps(json.dumps(
        dict(kind='emote-marker-v1',runId=run,nonce=nonce),sort_keys=True,separators=(',',':')))).replace('URL',json.dumps(url))
    raw=body.encode('utf-8');companion=b'module.exports = {kind: "emote-marker-v1"};\n'
    return {'script.js':raw,'companion.js':companion,'script-bundle/main.js':raw,'script-bundle/companion.js':companion}


class OwnedEmoteMarkerFiles(OwnedScriptFiles):
    def owned(self):
        value=self.store.read()
        exact(value,{'contractVersion','markerFilesVersion','runId','ownerToken','binding','hashes','fixtureUrl','ticket','nonce'})
        need(type(value['contractVersion']) is int and value['contractVersion']==1
            and type(value['markerFilesVersion']) is int and value['markerFilesVersion']==VERSION
            and context(value['binding'])==self.binding and type(value['ownerToken']) is str
            and re.fullmatch('[0-9a-f]{64}',value['ownerToken']))
        raw=originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce'])
        need(value['hashes']=={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()});return deepcopy(value)

    def reserve_marker(self,run,fixture_url,ticket):
        need(self.store.read() is None);nonce=secrets.token_hex(16);raw=originals(run,fixture_url,ticket,nonce)
        value=dict(contractVersion=1,markerFilesVersion=VERSION,runId=run,ownerToken=secrets.token_hex(32),binding=self.binding,
            fixtureUrl=fixture_url,ticket=ticket,nonce=nonce,hashes={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()})
        self.store.write(value,None);return self.owned()

    def reserve(self,run):
        need(False) # Explicit fixture origin and initial ticket are mandatory.

    def stage_reserved(self):
        value=self.owned();raw=originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce'])
        self.native.request('stage',value['runId'],value['ownerToken'],raw)
        return self.verify()

    def verify(self):
        value=self.owned();source=self.native.request('observe',value['runId'],value['ownerToken'])
        need(source['exists'] and all(row['exists'] for row in source['files']))
        expected=originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce'])
        actual={row['name']:base64.b64decode(row['base64'],validate=True) for row in source['files']}
        need(actual==expected);return source['directory']
