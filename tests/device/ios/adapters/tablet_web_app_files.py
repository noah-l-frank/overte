"""Ordinary Tablet-only parity app inputs using existing bounded Script files.

The canonical inline input is split across actual require modules; no native
file bound is raised and no HTTP page is relabelled as an inline document.
Loading/clicking/Script execution and resource retirement are separate owners.
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
from feature_journeys.browser_fixture import inline_data_url
from feature_journeys.fixtures import pinned_resource

VERSION=2
READS=(1,2)
LABELS={'open':'WEB TEST','inline':'WEB INLINE','return':'WEB RETURN'}


def originals(feature_run,fixture_url,ticket,nonce,*,version=VERSION):
    need(type(version) is int and version in READS)
    for value in (feature_run,ticket,nonce):identifier(value)
    resource_root(fixture_url,feature_run)
    inline=inline_data_url(feature_run,ticket,fixture_url)
    original=pinned_resource('web-source/client.js').decode()
    respond=original.split('    function respond(',1)[1].split('    function worldEvent(',1)[0]
    respond='    function respond('+respond
    body='''"use strict";
(function () {
    var metadata=Script.require("./script-bundle/companion.js");
    var inline=Script.require("./companion.js")+Script.require("./script-bundle/main.js");
    var tablet=Tablet.getTablet("com.highfidelity.interface.tablet.system"), stopped=false;
    var buttons={};
__OVT_TABLET_APP_RESPOND__
    function tabletEvent(message) {
        if (!stopped) respond(message,"tablet",function (reply) { tablet.emitScriptEvent(reply); });
    }
    function open() { if (!stopped) tablet.gotoWebScreen(__OVT_TABLET_APP_HTTP__); }
    function openInline() { if (!stopped) tablet.gotoWebScreen(inline); }
    function returnToReference() { if (!stopped) tablet.gotoWebScreen(__OVT_TABLET_APP_REFERENCE__); }
    var handlers={open:open,inline:openInline,return:returnToReference};
    Object.keys(handlers).forEach(function (key) {
        buttons[key]=tablet.addButton({text:__OVT_TABLET_APP_LABELS__[key],semanticId:"tablet-web-app."+__OVT_TABLET_APP_RUN__+"."+__OVT_TABLET_APP_NONCE__+"."+key,fixtureUrl:__OVT_TABLET_APP_FIXTURE__,sortOrder:200});
        buttons[key].clicked.connect(handlers[key]);
    });
    tablet.webEventReceived.connect(tabletEvent);
    Script.scriptEnding.connect(function () {
        stopped=true;
        tablet.webEventReceived.disconnect(tabletEvent);
        Object.keys(buttons).forEach(function (key) {
            buttons[key].clicked.disconnect(handlers[key]);tablet.removeButton(buttons[key]);
        });
        // The owning normal UI flow closes its actually owned page first.
        // Ending this Script never navigates or closes an unrelated page.
    });
}());
'''
    values={'RESPOND':respond,'HTTP':json.dumps(fixture_url+'tickets/'+ticket+'/index.html'),
            'REFERENCE':json.dumps(fixture_url+'tickets/'+ticket+'/reference.html'),'LABELS':json.dumps(LABELS,sort_keys=True),
            'RUN':json.dumps(feature_run),'NONCE':json.dumps(nonce),'FIXTURE':json.dumps(fixture_url)}
    expression=r'__OVT_TABLET_APP_(RESPOND|HTTP|REFERENCE|LABELS|RUN|NONCE|FIXTURE)__'
    if version==1:
        # Preserve the exact already-written v1 inputs, including the old
        # sequential substitution grammar. They are historical ownership, not
        # current source-qualified app controls. Never silently upgrade bytes.
        body=body.replace(',fixtureUrl:__OVT_TABLET_APP_FIXTURE__','')
        body=re.sub(expression,lambda match:match[1],body)
        for key,value in values.items():
            if key!='FIXTURE':body=body.replace(key,value)
    else:body=re.sub(expression,lambda match:values[match[1]],body)
    split=(len(inline)+1)//2
    module=lambda text:('module.exports='+json.dumps(text,ensure_ascii=True,separators=(',',':'))+';\n').encode()
    metadata=dict(kind='tablet-web-app-v1',runId=feature_run,ticket=ticket,nonce=nonce,inlineSha256=hashlib.sha256(inline.encode()).hexdigest())
    files={'script.js':body.encode(),'companion.js':module(inline[:split]),'script-bundle/main.js':module(inline[split:]),
        'script-bundle/companion.js':('module.exports='+json.dumps(metadata,sort_keys=True,separators=(',',':'))+';\n').encode()}
    need(set(files)==set(NAMES) and all(0<len(raw)<=8192 for raw in files.values()))
    return files


class OwnedTabletWebAppFiles(OwnedScriptFiles):
    def owned(self):
        value=self.store.read()
        exact(value,{'contractVersion','tabletWebAppFilesVersion','runId','featureRun','ownerToken','binding','hashes','fixtureUrl','ticket','nonce'})
        need(type(value['contractVersion']) is int and value['contractVersion']==1
            and type(value['tabletWebAppFilesVersion']) is int and value['tabletWebAppFilesVersion'] in READS
            and context(value['binding'])==self.binding and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['ownerToken']))
        identifier(value['runId']);need(value['runId']!=value['featureRun'])
        raw=originals(value['featureRun'],value['fixtureUrl'],value['ticket'],value['nonce'],version=value['tabletWebAppFilesVersion'])
        need(value['hashes']=={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()});return deepcopy(value)

    def reserve_app(self,feature_run,fixture_url,ticket):
        need(self.store.read() is None);nonce=secrets.token_hex(16);storage=secrets.token_hex(16);need(storage!=feature_run)
        raw=originals(feature_run,fixture_url,ticket,nonce)
        value=dict(contractVersion=1,tabletWebAppFilesVersion=VERSION,runId=storage,featureRun=feature_run,ownerToken=secrets.token_hex(32),
            binding=self.binding,fixtureUrl=fixture_url,ticket=ticket,nonce=nonce,hashes={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()})
        self.store.write(value,None);return self.owned()

    def reserve(self,run):need(False)

    def stage_reserved(self):
        value=self.owned();raw=originals(value['featureRun'],value['fixtureUrl'],value['ticket'],value['nonce'],version=value['tabletWebAppFilesVersion'])
        self.native.request('stage',value['runId'],value['ownerToken'],raw);return self.verify()

    def verify(self):
        value=self.owned();source=self.native.request('observe',value['runId'],value['ownerToken'])
        need(source['exists'] and all(row['exists'] for row in source['files']))
        expected=originals(value['featureRun'],value['fixtureUrl'],value['ticket'],value['nonce'],version=value['tabletWebAppFilesVersion'])
        need({row['name']:base64.b64decode(row['base64'],validate=True) for row in source['files']}==expected)
        return source['directory']
