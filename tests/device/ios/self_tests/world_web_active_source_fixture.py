"""Live Node product input/reference/observer; native and SDK delivery modeled.

The Node document remains alive across ordinary W3C actions. Source and control
models retain actual evaluated DOM output; they never fill an expected editor
value or synthesize an echo as the consequence of an acknowledged POST.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from adapters.normal_ui import NativeUI
from ios.adapters.world_web_geometry import point
from ios.self_tests.world_web_sources_fixture import SDK,EPOCH
from ios.self_tests.world_web_source_fixture import OriginalSources,URL
from ios.self_tests.test_ios_world_web_geometry import originals as geometry_originals


class ActiveSDK(SDK):
    def __init__(self):
        super().__init__();self.fixture_url=URL;geometry,_doc,self.world,_ui,self.entity=geometry_originals()
        self.world['runId']='a'*32;self.world['processId']=42;self.world['source']['scriptOriginal']['processId']=42
        ownership=json.dumps(dict(kind='emote-marker-v1',runId='a'*32,nonce='b'*32),sort_keys=True,separators=(',',':'))
        self.world['source']['markers'][0]['userData']=ownership;geometry['source']['entities'][0]['userData']=ownership
        self.world['source']['scriptOriginal']['source']['effects']['entities'][0]['userData']=ownership
        self.page_source=OriginalSources(clock_ms=self.tick,monotonic_ms=lambda:round(self.time*1000),source_identity='web-entity:'+self.entity)
        self.browser=self.page_source.browser;self.world['source']['markers'][0]['sourceUrl']=self.page_source.identity['sourceUrl']
        geometry['source']['entities'][0]['sourceUrl']=self.page_source.identity['sourceUrl'];self.actual_geometry=geometry['source']
        self.process=subprocess.Popen(['node',str(Path(__file__).with_name('world_web_page_fixture.js'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.page=self.evaluate(dict(op='open',bridge=True,url=self.page_source.url,html=self.page_source.body.decode()))
        self.shift=False;self.posted=[];self.releases=0;self.lose=False;self.before_post=None;self.after_post=None
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=5);self.process.stdout.close();self.process.stderr.close()
    def evaluate(self,query):
        query=dict(query,epoch=self.tick());self.process.stdin.write(json.dumps(query)+'\n');self.process.stdin.flush()
        value=json.loads(self.process.stdout.readline());assert 'error' not in value,value.get('error')
        self.time=max(self.time,(value['epoch']-EPOCH)/1000);return value
    def owner(self,*args,**kwargs):
        source=super().owner(*args,**kwargs);source.phase.client.url=URL.split('/runs/')[0];source.phase.fixture_url=URL;return source
    def original(self,name):
        if name=='document':
            query=self.queries[name];self.page=self.evaluate(dict(op='read',requestId=query['commandId']))
            self.page_source.dom_sequence+=1;stamp=self.tick();body=deepcopy(self.page['document']);assert body['requestId']==query['commandId']
            return json.dumps(dict(iosWorldWebDOMNativeVersion=1,commandId=query['commandId'],runId=self.world['runId'],surface='world',instance='e'*32,
                sequence=self.page_source.dom_sequence,processId=42,capturedEpochMs=stamp,status='ready',source=dict(nativeView=deepcopy(self.page_source.view),dom=body)))
        if name=='ledger':
            query=self.queries[name];value=self.page_source.ledger(query);assert value['fixtureUrl']==query['fixtureUrl'];return json.dumps(value)
        value=json.loads(super().original(name))
        if name=='geometry':value['source']=deepcopy(self.actual_geometry)
        return json.dumps(value)
    def ui(self):
        value=object.__new__(NativeUI);value._check=lambda:None;value.release_actions=self.release
        value._request=self.request;return value
    def release(self):self.releases+=1
    def request(self,method,path,body=None):
        if method=='GET' and path=='/window/rect':return dict(x=0,y=0,width=1024,height=768)
        assert method=='POST' and path=='/actions'
        if self.before_post is not None:self.before_post()
        from adapters.operation_transport_guard import check
        check();self.posted.append(deepcopy(body))
        if self.lose:raise OSError('Modeled unknown W3C POST')
        for source in body['actions']:
            if source['type']=='pointer':
                position=None
                for action in source['actions']:
                    if action['type']=='pointerMove':position=(action['x'],action['y'])
                    if action['type'] not in ('pointerDown','pointerUp'):continue
                    assert position is not None
                    # Invert the actual submitted screen ray against the same
                    # explicit camera/entity plane. No requested control ID
                    # participates in hit testing or the evaluated product JS.
                    import math
                    camera=self.actual_geometry['view'];entity=self.actual_geometry['entities'][0];distance=camera['position'][2]-entity['position'][2]
                    nx=(position[0]-512)/512;ny=1-(position[1]-20)/728*2
                    world_x=camera['position'][0]+nx*distance*math.tan(math.radians(camera['fieldOfViewDegrees'])/2)*camera['aspectRatio']
                    world_y=camera['position'][1]+ny*distance*math.tan(math.radians(camera['fieldOfViewDegrees'])/2)
                    x=((world_x-entity['position'][0])/entity['dimensions'][0]+entity['registrationPoint'][0])*850
                    y=(1-entity['registrationPoint'][1]-(world_y-entity['position'][1])/entity['dimensions'][1])*661
                    kind='press' if action['type']=='pointerDown' else 'release';entry=self.page_source.event('pointer-enter',dict(type=kind,x=x,y=y,width=850,height=661,button=0,codeSha256='a'*64))
                    self.page=self.evaluate(dict(op='pointer',args=[kind,x,y,0]));self.page_source.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False,result=True)))
                    self.page_source.event('callback-return',dict(entry=entry['sequence']))
            else:
                assert source['type']=='key'
                for action in source['actions']:
                    key=action['value']
                    if key=='\ue008':self.shift=action['type']=='keyDown';continue
                    if action['type']!='keyDown':continue
                    qt={'\ue010':16777233,'\ue011':16777232,'\ue003':16777219}.get(key,0);text='' if qt else key
                    entry=self.page_source.event('key-enter',dict(text=text,key=qt,modifiers=33554432 if self.shift else 0))
                    self.page=self.evaluate(dict(op='key',args=[text,qt,self.shift]));self.page_source.event('signal-return',dict(entry=entry['sequence']))
        if self.after_post is not None:self.after_post()
        return None
