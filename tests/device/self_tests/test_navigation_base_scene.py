"""Actual static-input HTTP/byte/history tests, without native or device use."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import secrets
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_ui import NativeUIError
from feature_journeys import navigation_base_scene as base
from feature_journeys.navigation_fixture import NavigationResources
from feature_journeys.server import Handler
from self_tests import test_navigation_scene as scene_tests


class NavigationBaseSceneTests(unittest.TestCase):
    def setUp(self):
        self.harness=scene_tests.NavigationSceneTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        self.provider=self.harness.provider;self.client=self.harness.client;self.url=base.resource_url(self.harness.inputs['sceneUrl'])
        self.path=urlsplit(self.url).path
    def status(self):
        value=self.client.request('/navigation-base-scene');self.validate(value);return value
    def validate(self,value,previous=None):
        return base.validate_status(value,instance=self.provider.instance,scene_url=self.harness.inputs['sceneUrl'],
            source_revision=self.harness.inputs['sourceRevision'],previous=previous)

    def test_actual_static_bytes_are_available_before_registration_and_remain_identical_after_retirement(self):
        before=self.status();self.assertTrue(before['available']);self.assertEqual([],before['responses'])
        code,raw,id=self.harness.get(self.path);self.assertEqual(200,code);self.assertEqual(base.body(),raw)
        run=self.harness.open();self.harness.client.activate('c'*32,'open',{})
        self.assertEqual(raw,self.harness.get(self.path+'?location=/0,0,4/0,0,0,1')[1])
        self.harness.client.close();self.assertEqual(raw,self.harness.get(self.path)[1])
        value=self.status();self.validate(value,before);self.assertTrue(value['available']);self.assertEqual(3,len(value['responses']))
        self.assertEqual(id,value['responses'][0]['responseId']);self.assertEqual(hashlib.sha256(raw).hexdigest(),value['sha256'])
        self.assertEqual([],self.provider.scene_snapshot(run)['responses']);self.assertEqual([],self.provider.snapshot(run)['responses'])
        data=json.loads(raw);self.assertEqual(5,len(data['Entities']))
        self.assertTrue(all(row['type']=='Box' and not any(key in row for key in ('script','serverScripts','sourceUrl')) for row in data['Entities']))
        self.assertNotIn(run.encode(),raw);self.assertNotIn(b'navigation-marker',raw)

    def test_dynamic_marker_scene_and_static_base_have_separate_actual_socket_histories(self):
        run=self.harness.open();self.harness.get(self.path);code,raw,_=self.harness.get('/navigation/scene.json')
        self.assertEqual(200,code);self.assertEqual(6,len(json.loads(raw)['Entities']))
        self.assertEqual(1,len(self.status()['responses']));self.assertEqual(1,len(self.provider.scene_snapshot(run)['responses']))
        self.assertEqual([],self.provider.snapshot(run)['responses'])

    def test_legacy_directory_provider_does_not_enable_the_static_route_or_status(self):
        self.harness.server.navigation_resources=NavigationResources(self.harness.inputs)
        self.assertEqual(404,self.harness.get(self.path)[0])
        with self.assertRaises(ValueError):self.client.request('/navigation-base-scene')

    def test_foreign_host_unknown_query_duplicate_viewpoint_or_wrong_method_cannot_serve_base(self):
        for path,headers in ((self.path,{'Host':'foreign.invalid'}),(self.path+'?run=foreign',{}),
                (self.path+'?location=/99,0,4/0,0,0,1',{}),
                (self.path+'?location=/0,0,4/0,0,0,1&location=/0,0,4/0,0,0,1',{})):
            with self.subTest(path=path):self.assertEqual(404,self.harness.get(path,headers)[0])
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url,data=b'{}',method='POST'),timeout=2)
        try:self.assertEqual(404,result.exception.code)
        finally:result.exception.close()
        self.assertEqual([],self.status()['responses'])

    def test_adapter_reader_can_inspect_only_input_metadata_and_cannot_activate_or_register(self):
        token=secrets.token_hex(32);self.harness.server.adapter_token=token
        adapter=AdapterFixtureClient(self.client.url,token)
        self.validate(adapter.request('/navigation-base-scene'))
        with self.assertRaises(NativeUIError):adapter.register('world-navigation')
        with self.assertRaises(NativeUIError):adapter.request('/runs',dict(area='world-navigation'))
        self.assertEqual({},self.provider.runs)

    def test_unknown_failed_socket_write_poisoning_cannot_return_successful_empty_history(self):
        parsed=urlsplit(self.url)
        with self.assertRaises(OSError):
            with self.provider.scene_response(parsed.path,'',request_authority=parsed.netloc,request_scheme=parsed.scheme) as response:
                self.assertIsNotNone(response);raise OSError('Synthetic failed original socket write')
        value=self.provider.base_snapshot();self.assertFalse(value['complete']);self.assertFalse(value['available'])
        with self.assertRaises(ValueError):self.validate(value)
        self.assertEqual(404,self.harness.get(self.path)[0])

    def test_status_waits_until_the_actual_bounded_socket_write_has_finished(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();result=[];snapshots=[];errors=[]
        original=Handler.send
        def blocked(handler,status,data,*args,**kwargs):
            if handler.path==self.path:
                entered.set()
                if not release.wait(2):raise AssertionError('Synthetic owned socket was not released')
            return original(handler,status,data,*args,**kwargs)
        def fetch():
            try:result.append(self.harness.get(self.path))
            except Exception as error:errors.append(error)
        def status():
            try:snapshots.append(self.provider.base_snapshot())
            except Exception as error:errors.append(error)
            finally:done.set()
        with patch.object(Handler,'send',blocked):
            worker=threading.Thread(target=fetch);observer=threading.Thread(target=status);worker.start()
            try:
                self.assertTrue(entered.wait(2));observer.start();self.assertFalse(done.wait(.05))
            finally:
                release.set();worker.join(timeout=3)
                if observer.ident is not None:observer.join(timeout=3)
        self.assertFalse(worker.is_alive());self.assertFalse(observer.is_alive());self.assertEqual([],errors)
        self.assertEqual(200,result[0][0]);self.assertEqual(1,len(snapshots[0]['responses']));self.validate(snapshots[0])

    def test_receipt_body_source_instance_counts_and_old_prefix_cannot_be_relabelled(self):
        self.harness.get(self.path);old=self.status();self.harness.get(self.path);current=self.status();self.validate(current,old)
        for fault in ('instance','url','body','bytes','revision','history','count','ticket','time'):
            value=deepcopy(current)
            if fault=='instance':value['instance']='f'*32
            elif fault=='url':value['url']+='-foreign'
            elif fault=='body':value['sha256']='f'*64
            elif fault=='bytes':value['bytes']+=1
            elif fault=='revision':value['sourceRevision']='f'*40
            elif fault=='history':value['responses'][0]['responseId']='f'*32
            elif fault=='count':value['responses'][0]['sequence']=True
            elif fault=='ticket':value['responses'][0]['ticket']='f'*32
            else:value['responses'][0]['completedEpochMs']=value['capturedEpochMs']+1
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.validate(value,old)

