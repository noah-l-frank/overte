"""Actual owned loopback scene/marker inputs; no client renderer or devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.navigation_scene import PROFILE,scene
from feature_journeys.navigation_fixture import NavigationResources,validate_status,DIRECTORY,QUERY
from feature_journeys.fixtures import marker_bytes
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.engine import Journey
from navigation_observation import FIXTURE_MARKERS
from self_tests.test_navigation_resources import INPUTS,TICKET

class NavigationSceneTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(self.reader,self.actor);self.origin=f'http://127.0.0.1:{self.server.server_port}'
        self.inputs=dict(INPUTS,sceneUrl=self.origin+'/scene.json')
        self.provider=NavigationResources(self.inputs,scene_profile=PROFILE);self.server.navigation_resources=self.provider
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.client=Client(self.origin+'/feature-fixture/v1',self.reader)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)
    def open(self):
        run,_=self.client.register('world-navigation');self.client.activate(TICKET);return run
    def fetch(self,path,*,headers=None):
        try:
            with urlopen(Request(self.origin+path,headers=headers or {}),timeout=2) as r:return r.status,r.read(),r.headers.get('X-Overte-Fixture-Response')
        except HTTPError as e:
            try:return e.code,e.read(),e.headers.get('X-Overte-Fixture-Response')
            finally:e.close()
    def test_explicit_profile_serves_original_geometry_owned_cues_and_completed_scene_receipt(self):
        run=self.open();status,raw,nonce=self.fetch('/scene.json?location=/2,0,4/0,0,0,1')
        self.assertEqual(200,status);document=json.loads(raw);base=json.loads((Path(__file__).resolve().parents[1]/'fixture/scene.json').read_text())
        self.assertEqual(base['Paths'],document['Paths']);self.assertEqual(base['Entities'][:-1],document['Entities'][:len(base['Entities'])-1])
        self.assertEqual(33,len(document['Entities']));self.assertTrue(set(FIXTURE_MARKERS).issubset({e['name'] for e in document['Entities']}))
        carriers=[e for e in document['Entities'] if e['type']=='Web'];self.assertEqual(3,len(carriers))
        self.assertEqual(3,len({e['position']['x'] for e in carriers}))
        self.assertTrue(all(e['sourceUrl']==self.origin+'/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/navigation-marker.v1.html' for e in carriers))
        source=self.client.navigation_status();self.assertEqual(PROFILE,source['sceneProfile']);self.assertEqual(2,source['navigationProviderVersion'])
        receipt=source['responses'][0];self.assertEqual(('stereo-scene',nonce,len(raw),hashlib.sha256(raw).hexdigest()),
            (receipt['kind'],receipt['responseId'],receipt['bytes'],receipt['sha256']))
        self.assertEqual(200,self.fetch(DIRECTORY+'?'+QUERY)[0]);self.client.close();self.assertEqual(404,self.fetch('/scene.json')[0])
    def test_same_original_marker_document_reads_current_challenge_and_keeps_original_interactable_script(self):
        run=self.open();_,raw,_=self.fetch('/scene.json');document=json.loads(raw)
        marker=next(e['sourceUrl'] for e in document['Entities'] if e['type']=='Web')
        status,html,_=self.fetch(marker[len(self.origin):]);self.assertEqual(200,status)
        self.assertIn(b'Owned Navigation marker',html);self.assertIn(b'setInterval(refresh,100)',html)
        old=self.fetch('/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/marker.png')[1]
        self.client.activate('9'*32);self.assertEqual('9'*32,json.loads(self.fetch('/feature-fixture/v1/runs/'+run+'/current')[1])['ticket'])
        new=self.fetch('/feature-fixture/v1/runs/'+run+'/tickets/'+'9'*32+'/marker.png')[1]
        self.assertNotEqual(old,new);self.assertEqual(marker_bytes(run,'9'*32),new)
        script=next(e['script'] for e in document['Entities'] if e.get('script'))
        self.assertEqual((Path(__file__).resolve().parents[1]/'fixture/scripted_interactable.js').read_bytes(),self.fetch(script[len(self.origin):])[1])
        self.client.close()
    def test_unselected_profile_foreign_authority_bad_viewpoints_or_retired_run_do_not_serve_owned_scene(self):
        self.assertEqual(404,self.fetch('/scene.json')[0]);run=self.open()
        for path,headers in (('/scene.json?location=/99,0,4',{}),('/scene.json?desired=B',{}),('/scene.json',{'Host':'foreign.invalid'})):
            self.assertEqual(404,self.fetch(path,headers=headers)[0])
        self.assertEqual([],self.client.navigation_status()['responses'])
        self.server.navigation_resources=NavigationResources(self.inputs)
        self.assertEqual(404,self.fetch('/scene.json')[0]);self.server.navigation_resources=self.provider;self.client.close()
    def test_missing_partial_foreign_or_duplicate_original_scene_write_poison_source(self):
        for fault in ('missing','bytes','id','duplicate','failure'):
            provider=NavigationResources(self.inputs,scene_profile=PROFILE);provider.provision('a'*32);provider.activate('a'*32,TICKET)
            with self.subTest(fault=fault),self.assertRaises((ValueError,OSError)):
                with provider.scene_response('/scene.json','',request_authority=self.origin.split('://')[1],request_scheme='http') as response:
                    status,raw,nonce,write=response
                    if fault=='failure':raise OSError('Synthetic failed socket write')
                    if fault!='missing':
                        actual=dict(status=status,responseId=nonce,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                        if fault=='bytes':actual['bytes']-=1
                        elif fault=='id':actual['responseId']='8'*32
                        write(actual)
                        if fault=='duplicate':write(actual)
            self.assertFalse(provider.ready()['ready']);self.assertEqual([],provider.snapshot('a'*32)['responses'])
    def test_profile_history_size_bound_and_original_configuration_cannot_change(self):
        run=self.open();self.fetch('/scene.json');before=self.client.navigation_status()
        for edit in (lambda v:v.update(sceneProfile='foreign'),lambda v:v.update(navigationProviderVersion=1),
                     lambda v:v['responses'][0].update(bytes=1048577),lambda v:v['responses'][0].update(kind='directory')):
            value=deepcopy(before);edit(value)
            with self.subTest(edit=edit),self.assertRaises(ValueError):validate_status(value,instance=self.provider.instance,run=run,inputs=self.inputs,previous=before)
        self.provider.scene_profile=None
        with self.assertRaises(ValueError):self.client.navigation_status()
    def test_constructor_profile_scene_url_and_origin_are_closed(self):
        for profile in (True,'graphics','pico-navigation-scene-v2'):
            with self.assertRaises(ValueError):NavigationResources(self.inputs,scene_profile=profile)
        for origin in ('file:///tmp','http://a.invalid/private','http://user:secret@a.invalid','http://a.invalid?desired=A'):
            with self.assertRaises(ValueError):scene('a'*32,TICKET,origin)

if __name__=='__main__':unittest.main()
