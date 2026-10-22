"""Owned ordinary world-only variant of the pinned parity client script.

Staging is input delivery. Only actual native/script/entity/DOM originals can
establish execution, document consumption, echo delivery or lifetime retirement.
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
from adapters.native_script_files import OwnedScriptFiles
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from feature_journeys.fixtures import pinned_resource
from feature_journeys.navigation_scene import resource_root

VERSION=1


def originals(run,fixture_url,ticket,nonce):
    identifier(run);identifier(ticket);identifier(nonce);resource_root(fixture_url,run)
    base=pinned_resource('web-source/client.js').decode('utf-8')
    start=base.index('    function respond(');end=base.index('    function worldEvent(')
    respond=base[start:end]
    # Keep the original actual echo protocol. This ordinary fixture owns only
    # one local world Entity and no unrelated tablet app/button resources.
    script='''"use strict";
(function () {
    var companion = Script.require("./companion.js");
    var page = PAGE, injected = INJECTED, entity = null, stopped = false, call = 0;
    var observer = typeof Test !== "undefined" && typeof Test.featureIOSWorldWebEvent === "function" ? Test : null;
    function event(kind, sequence, payload) {
        if (observer) observer.featureIOSWorldWebEvent({worldWebWorkEventVersion:1,runId:RUN,nonce:NONCE,event:kind,call:sequence,payload:payload});
    }
    function tracked(kind, payload, closure) {
        if (!observer) return closure();
        var sequence = ++call;
        event(kind + "-enter", sequence, payload);
        try { var result = closure(); event(kind + "-return", sequence, payload); return result; }
        finally { event(kind + "-finally", sequence, payload); }
    }
RESPOND
    function worldEvent(id, message) {
        if (!stopped && entity && String(id) === String(entity)) {
            return tracked("world-event", {entityId:String(id),message:message}, function () {
                return respond(message, "world", function (reply) {
                    return tracked("script-reply", {entityId:String(entity),message:reply}, function () {
                        return Entities.emitScriptEvent(entity, reply);
                    });
                });
            });
        }
    }
    entity = Entities.addEntity({type:"Web",name:NAME,userData:DATA,sourceUrl:page,scriptURL:injected,
        position:Vec3.sum(Camera.position,Vec3.multiplyQbyV(Camera.orientation,{x:0,y:0,z:-1.5})),rotation:Camera.orientation,
        dimensions:{x:1.8,y:1.4,z:0.01},dpi:12,maxFPS:30,grab:{grabbable:false},visible:true,collisionless:true},"local");
    Entities.webEventReceived.connect(worldEvent);
    event("loaded", 0, {entityId:entity ? String(entity) : null});
    Script.scriptEnding.connect(function () {
        return tracked("ending", {entityId:entity ? String(entity) : null}, function () {
            stopped = true;
            Entities.webEventReceived.disconnect(worldEvent);
            if (entity) Entities.deleteEntity(entity);
        });
    });
}());
'''
    replacements=dict(PAGE=json.dumps(fixture_url+'tickets/'+ticket+'/reference.html'),
        INJECTED=json.dumps(fixture_url+'tickets/'+ticket+'/injected.js'),RUN=json.dumps(run),NONCE=json.dumps(nonce),
        RESPOND=respond,NAME=json.dumps('e2e-'+run+'-script'),DATA=json.dumps(json.dumps(
            # This is the existing generic owned Web marker inventory grammar;
            # it claims no Emote action. This Web surface carries normal input.
            dict(kind='emote-marker-v1',runId=run,nonce=nonce),sort_keys=True,separators=(',',':'))))
    for key,value in replacements.items():script=script.replace(key,value)
    raw=script.encode('utf-8');companion=b'module.exports = {kind:"world-web-v1"};\n'
    return {'script.js':raw,'companion.js':companion,'script-bundle/main.js':raw,'script-bundle/companion.js':companion}


class OwnedWorldWebFiles(OwnedScriptFiles):
    def owned(self):
        value=self.store.read()
        exact(value,{'contractVersion','worldWebFilesVersion','runId','ownerToken','binding','hashes','fixtureUrl','ticket','nonce','baseSourceSha256'})
        need(type(value['contractVersion']) is int and value['contractVersion']==1 and type(value['worldWebFilesVersion']) is int
            and value['worldWebFilesVersion']==VERSION and context(value['binding'])==self.binding
            and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['ownerToken'])
            and value['baseSourceSha256']==hashlib.sha256(pinned_resource('web-source/client.js')).hexdigest())
        raw=originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce'])
        need(value['hashes']=={name:hashlib.sha256(body).hexdigest() for name,body in raw.items()});return deepcopy(value)
    def reserve_web(self,run,fixture_url,ticket):
        need(self.store.read() is None);nonce=secrets.token_hex(16);raw=originals(run,fixture_url,ticket,nonce)
        value=dict(contractVersion=1,worldWebFilesVersion=VERSION,runId=run,ownerToken=secrets.token_hex(32),binding=self.binding,
            fixtureUrl=fixture_url,ticket=ticket,nonce=nonce,baseSourceSha256=hashlib.sha256(pinned_resource('web-source/client.js')).hexdigest(),
            hashes={name:hashlib.sha256(body).hexdigest() for name,body in raw.items()})
        self.store.write(value,None);return self.owned()
    reserve_marker=reserve_web
    def reserve(self,run):need(False)
    def stage_reserved(self):
        value=self.owned();self.native.request('stage',value['runId'],value['ownerToken'],
            originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce']))
        return self.verify()
    def verify(self):
        value=self.owned();actual=self.native.request('observe',value['runId'],value['ownerToken'])
        need(actual['exists'] and all(row['exists'] for row in actual['files']))
        bodies={row['name']:base64.b64decode(row['base64'],validate=True) for row in actual['files']}
        need(bodies==originals(value['runId'],value['fixtureUrl'],value['ticket'],value['nonce']));return actual['directory']
