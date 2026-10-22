"""Actual local HTTP scene/marker inputs; no native/client/device rendering."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from feature_journeys.fixtures import payload,marker_bytes
from feature_journeys.navigation_fixture import NavigationResources
from feature_journeys.navigation_scene import scene,marker_id,PROFILE,MARKER_RESOURCE,validate_status
from feature_journeys.server import make_server,Handler
from feature_journeys.witness import Client
from self_tests.test_navigation_resources import INPUTS,TICKET


class NavigationSceneTests(unittest.TestCase):
    def setUp(self):
        reader,actor=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(reader,actor);self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.inputs=INPUTS|dict(sceneUrl=self.origin+'/navigation/scene.json')
        self.provider=NavigationResources(self.inputs,scene_profile=PROFILE);self.server.navigation_resources=self.provider
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop);self.client=Client(self.origin+'/feature-fixture/v1',reader)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)
    def open(self):
        run,_=self.client.register('world-navigation');self.client.activate(TICKET)
        return run
    def get(self,path,headers=None):
        try:
            with urlopen(Request(self.origin+path,headers=headers or {}),timeout=2) as reply:
                return reply.status,reply.read(),reply.headers.get('X-Overte-Fixture-Response')
        except HTTPError as error:
            try:return error.code,error.read(),error.headers.get('X-Overte-Fixture-Response')
            finally:error.close()

    def test_scene_is_an_opt_in_normal_input_with_actual_original_socket_bytes(self):
        run=self.open();status,raw,response=self.get('/navigation/scene.json?location=/0,0,4/0,0,0,1')
        self.assertEqual(200,status);data=json.loads(raw);root=self.origin+'/feature-fixture/v1/runs/'+run+'/'
        self.assertEqual(scene(run,TICKET,root),data)
        original=json.loads((Path(__file__).resolve().parents[1]/'fixture'/'scene.json').read_text())
        self.assertEqual(original['Entities'][:5],data['Entities'][:5]);self.assertEqual(6,len(data['Entities']))
        marker=data['Entities'][-1];self.assertEqual('{'+marker_id(run)+'}',marker['id']);self.assertEqual('Web',marker['type'])
        self.assertTrue(marker['collisionless']);self.assertEqual(root+'tickets/'+TICKET+'/'+MARKER_RESOURCE,marker['sourceUrl'])
        snapshot=self.client.navigation_scene_status();row=snapshot['responses'][0]
        self.assertEqual(response,row['responseId']);self.assertEqual(len(raw),row['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256']);self.assertEqual(TICKET,row['ticket'])
        self.assertEqual([],self.client.navigation_status()['responses'])
        self.assertNotIn('passed',snapshot);self.assertNotIn('rendered',snapshot)

    def test_same_original_marker_document_follows_actual_current_ticket_without_rewriting_scene(self):
        run=self.open();_,raw,_=self.get('/navigation/scene.json');marker=json.loads(raw)['Entities'][-1]
        path=marker['sourceUrl'][len(self.origin):];status,html,_=self.get(path);self.assertEqual(200,status)
        self.assertIn(b'Owned Navigation marker',html);self.assertIn(b'cache:"no-store"',html)
        self.assertIn(b'/current',html);self.assertNotIn(TICKET.encode(),html)
        _,first,_=self.get('/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/marker.png')
        self.client.activate('c'*32,'directory-select',dict(destination='owned-place-'+run))
        _,again,_=self.get(path);self.assertEqual(html,again)
        _,current,_=self.get('/feature-fixture/v1/runs/'+run+'/current');self.assertEqual('c'*32,json.loads(current)['ticket'])
        _,second,_=self.get('/feature-fixture/v1/runs/'+run+'/tickets/'+'c'*32+'/marker.png')
        self.assertEqual(marker_bytes(run,TICKET),first);self.assertEqual(marker_bytes(run,'c'*32),second);self.assertNotEqual(first,second)

    def test_actual_marker_javascript_fetches_real_loopback_current_and_png(self):
        run=self.open();_,raw,_=self.get('/navigation/scene.json');url=json.loads(raw)['Entities'][-1]['sourceUrl']
        program=r'''
(async()=>{
const origin=ORIGIN;const html=await (await fetch(URL)).text();const code=html.match(/<script>([\s\S]*)<\/script>/)[1];
let src='',timer=null;const image={getAttribute:()=>src,set src(v){src=v}};
global.document={querySelector:selector=>{if(selector!=='#marker')throw Error('foreign selector');return image}};
global.setInterval=(fn,ms)=>{if(ms!==100)throw Error('unbounded refresh');timer=fn;};
const nativeFetch=global.fetch;global.fetch=(url,options)=>nativeFetch(new URL(url,origin),options);
eval(code);
for(let attempt=0;attempt<100&&!src;attempt++)await new Promise(resolve=>setTimeout(resolve,5));
if(!src||!timer)throw Error('marker never received a current ticket');
const response=await fetch(src);if(response.status!==200)throw Error('PNG unavailable');
const raw=Buffer.from(await response.arrayBuffer());if(raw.length<32||raw[1]!==80||raw[2]!==78||raw[3]!==71)throw Error('not PNG');
if(src!==EXPECTED)throw Error('foreign run or ticket');
})().catch(()=>{process.exitCode=1});
'''.replace('ORIGIN',json.dumps(self.origin)).replace('URL',json.dumps(url),1).replace('EXPECTED',json.dumps('/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/marker.png'))
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_foreign_host_extra_query_or_unowned_viewpoint_cannot_select_scene_inputs(self):
        self.open()
        for path,headers in [('/navigation/scene.json',{'Host':'foreign.invalid'}),('/navigation/scene.json?run=foreign',{}),
                ('/navigation/scene.json?location=/99,0,4/0,0,0,1',{}),('/navigation/scene.json?location=/0,0,4/0,0,0,1&location=/2,0,4/0,0,0,1',{}),
                ('/elsewhere/scene.json',{})]:
            with self.subTest(path=path):self.assertEqual(404,self.get(path,headers)[0])
        self.assertEqual([],self.client.navigation_scene_status()['responses'])

    def test_disabled_v1_provider_never_enables_the_scene_route(self):
        self.provider=NavigationResources(self.inputs);self.server.navigation_resources=self.provider;self.open()
        self.assertEqual(404,self.get('/navigation/scene.json')[0])
        with self.assertRaises(ValueError):self.client.navigation_scene_status()
        self.assertEqual(1,self.client.navigation_status()['navigationProviderVersion'])
        with self.assertRaises(ValueError):NavigationResources(self.inputs,scene_profile=True)

    def test_retirement_preserves_original_scene_receipts_and_blocks_future_marker_inputs(self):
        run=self.open();_,raw,_=self.get('/navigation/scene.json');marker_path=json.loads(raw)['Entities'][-1]['sourceUrl'][len(self.origin):]
        first=self.client.navigation_scene_status();self.client.close();after=self.client.navigation_scene_status()
        self.assertFalse(after['active']);self.assertIsNone(after['ticket']);self.assertEqual(first['responses'],after['responses'])
        for path in ('/navigation/scene.json',marker_path,'/feature-fixture/v1/runs/'+run+'/current',
                     '/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/marker.png'):
            expected=404 if path=='/navigation/scene.json' else 400  # Existing retired generic Journal boundary.
            self.assertEqual(expected,self.get(path)[0],path)
        validate_status(after,instance=self.provider.instance,run=run,scene_url=self.inputs['sceneUrl'],previous=first)
        self.client.close();self.assertEqual(after['responses'],self.client.navigation_scene_status()['responses'])

    def test_reusing_client_for_another_owned_run_resets_only_its_source_cursor(self):
        old=self.open();self.get('/navigation/scene.json');first=self.client.navigation_scene_status();self.client.close()
        run,_=self.client.register('world-navigation');self.client.activate('d'*32)
        self.assertNotEqual(old,run);current=self.client.navigation_scene_status()
        self.assertEqual([],current['responses']);self.assertEqual(first['responses'],self.provider.scene_snapshot(old)['responses'])
        self.client.close()

    def test_enabled_scene_profile_cannot_shadow_api_or_existing_fixture_resources(self):
        for path in ('/api/v1/places/scene.json','/feature-fixture/v1/scene.json'):
            with self.assertRaises(ValueError):NavigationResources(self.inputs|dict(sceneUrl=self.origin+path),scene_profile=PROFILE)

    def test_retirement_waits_for_the_original_scene_socket_write_owner(self):
        run=self.open();entered=threading.Event();release=threading.Event();retired=threading.Event();result=[]
        original=Handler.send
        def send(handler,*args,**kwargs):
            if handler.path=='/navigation/scene.json' and args[0]==200:
                entered.set()
                if not release.wait(1):raise RuntimeError('Test-owned scene write was not released')
            return original(handler,*args,**kwargs)
        fetch=threading.Thread(target=lambda:result.append(self.get('/navigation/scene.json')))
        retirement=threading.Thread(target=lambda:(self.provider.retire(run),retired.set()))
        with patch.object(Handler,'send',send):
            fetch.start()
            try:
                self.assertTrue(entered.wait(1));retirement.start()
                self.assertFalse(retired.wait(.025));release.set();fetch.join(2);retirement.join(2)
                self.assertFalse(fetch.is_alive());self.assertFalse(retirement.is_alive());self.assertTrue(retired.is_set())
            finally:
                release.set();fetch.join(2)
                if retirement.ident is not None:retirement.join(2)
        self.assertEqual(200,result[0][0]);snapshot=self.client.navigation_scene_status()
        self.assertFalse(snapshot['active']);self.assertEqual(1,len(snapshot['responses']));self.client.close()

    def test_failed_actual_scene_write_poison_cannot_become_empty_complete_history(self):
        run=self.open()
        with self.assertRaises(OSError):
            with self.provider.scene_response('/navigation/scene.json','',request_authority=self.origin.split('//')[1],request_scheme='http') as result:
                self.assertEqual(200,result[0]);raise OSError('modeled original socket write failed')
        self.assertFalse(self.provider.scene_snapshot(run)['complete']);self.assertEqual(404,self.get('/navigation/scene.json')[0])
        with self.assertRaises(ValueError):self.client.navigation_scene_status()

    def test_source_clock_history_receipts_and_retired_state_are_immutable(self):
        run=self.open();self.get('/navigation/scene.json');first=self.client.navigation_scene_status()
        for fault in ('hash','clock','resurrect'):
            value=deepcopy(first)
            if fault=='hash':value['responses'][0]['sha256']='f'*64
            elif fault=='clock':value['capturedEpochMs']=first['responses'][0]['completedEpochMs']-1
            else:value['active']=True;first=dict(first,active=False,ticket=None)
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_status(value,instance=self.provider.instance,
                run=run,scene_url=self.inputs['sceneUrl'],previous=first)

    def test_geometry_stimulus_rejects_foreign_resource_roots_and_changed_owned_namespaces(self):
        run=self.open();root=self.origin+'/feature-fixture/v1/runs/'+run+'/'
        for wrong in (root+'extra/',root.replace(run,'f'*32),root+'?wanted=true','file:///feature-fixture/v1/runs/'+run+'/'):
            with self.assertRaises(ValueError):scene(run,TICKET,wrong)
        self.assertNotEqual(marker_id(run),marker_id('f'*32))
        graphics=payload('graphics-marker.v1.html',run,TICKET)[1]
        navigation=payload(MARKER_RESOURCE,run,TICKET)[1]
        self.assertEqual(graphics.replace(b'Graphics',b'Navigation'),navigation.replace(b'overflow:hidden;',b'').replace(b'display:block;',b''))
        self.assertIn(b'img{display:block;',navigation);self.assertIn(b'overflow:hidden;',navigation)


if __name__=='__main__':unittest.main()
