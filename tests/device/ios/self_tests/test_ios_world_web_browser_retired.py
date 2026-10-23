"""Actual authenticated HTTP response archives; no native effect is inferred."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from adapters.normal_ui import NativeUIError
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.browser_retirement import MAX_ATTEMPTS,MAX_RUNS
from feature_journeys import browser_retirement as retired_http
from ios.adapters.world_web_measurements import browser_original


class WorldWebBrowserRetiredTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server('r'*64,'a'*64,adapter_token='d'*64)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start();self.addCleanup(self.close)
        self.base='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1';self.client=Client(self.base,'r'*64)
        self.run,_=self.client.register('world-web');self.client.activate('e'*32)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.assertFalse(self.thread.is_alive())
    def fetch(self,path,*,token=None,method='GET',value=None):
        request=Request(self.base+path,data=None if value is None else json.dumps(value).encode(),method=method,
            headers={} if token is None else dict(Authorization='Bearer '+token,**{'Content-Type':'application/json'}))
        try:response=urlopen(request,timeout=2)
        except HTTPError as error:response=error
        with response:return response.status,response.read()
    def archive(self):
        status,raw=self.fetch('/runs/'+self.run+'/browser-retired',token='d'*64);self.assertEqual(200,status)
        value=json.loads(raw);browser_original(value);return value
    def test_actual_close_keeps_response_bytes_identity_clocks_and_new_getter_is_readonly(self):
        path='/runs/'+self.run+'/tickets/'+'e'*32+'/reference.html';status,body=self.fetch(path);self.assertEqual(200,status)
        before=self.client.request('/runs/'+self.run+'/browser');self.assertEqual(hashlib.sha256(body).hexdigest(),before['responses'][0]['sha256'])
        self.client.close();self.assertFalse(self.server.browser_resources.has_run(self.run))
        after=self.archive();self.assertEqual(2,after['browserFixtureVersion']);self.assertEqual(self.run,after['retirement']['runId'])
        for name in ('instance','ready','sequence','responses'):self.assertEqual(before[name],after[name])
        self.assertEqual([],after['retirement']['attempts']);self.assertEqual(after,self.archive())
        status,_=self.fetch('/runs/'+self.run+'/browser',token='r'*64);self.assertEqual(400,status)
        changed=deepcopy(after);changed['responses'][0]['sha256']='0'*64
        with self.assertRaises(NativeUIError):browser_original(changed,after)
        returned=self.archive();returned['retirement']['attempts'].append({});self.assertEqual(after,self.archive())
    def test_auth_area_active_and_method_guards_never_expose_or_mutate_the_archive(self):
        path='/runs/'+self.run+'/browser-retired'
        self.assertEqual(400,self.fetch(path,token='r'*64)[0]);self.client.close()
        for token in (None,'x'*64):self.assertEqual(403,self.fetch(path,token=token)[0])
        for token in ('r'*64,'a'*64,'d'*64):self.assertEqual(200,self.fetch(path,token=token)[0])
        self.assertEqual(403,self.fetch(path,token='r'*64,method='POST',value={})[0])
        self.assertEqual(403,self.fetch('/runs/'+self.run+'/browser/control',token='a'*64,method='POST',value={'operation':'restore-resource'})[0])
        self.assertEqual(400,self.fetch('/runs/'+self.run+'/browser/control',token='r'*64,method='POST',value={'operation':'restore-resource'})[0])
        self.assertEqual(400,self.fetch('/runs/'+'f'*32+'/browser-retired',token='r'*64)[0])
        other=Client(self.base,'r'*64);run,_=other.register('emotes');other.activate('c'*32);other.close()
        self.assertEqual(400,self.fetch('/runs/'+run+'/browser-retired',token='r'*64)[0])
    def test_actual_late_resources_are_denied_and_actual_serialized_write_and_finally_are_visible(self):
        self.client.close();before=self.archive()
        for name in ('reference.html','client.js','marker.png','reference.mp4'):
            status,body=self.fetch('/runs/'+self.run+'/tickets/'+'e'*32+'/'+name);self.assertEqual(400,status)
            value=self.archive();browser_original(value,before);row=value['retirement']['attempts'][-1]
            self.assertEqual(name,row['resource']);self.assertEqual(status,row['headers']['status'])
            self.assertEqual(hashlib.sha256(body).hexdigest(),row['headers']['sha256']);self.assertEqual(len(body),row['write']['bytes'])
            self.assertIsNotNone(row['finallyEpochMs']);self.assertEqual(before['responses'],value['responses']);before=value
    def test_actual_inflight_denial_retains_pending_write_and_finally_without_inventing_drain(self):
        self.client.close();entered=threading.Event();release=threading.Event();values=[];errors=[]
        original=retired_http.headers
        def held(handler,body):
            original(handler,body)
            if getattr(handler,'browser_retired_attempt',None) is not None:
                entered.set()
                if not release.wait(2):raise RuntimeError('Controlled denial observation was not released')
        def request():
            try:values.append(self.fetch('/runs/'+self.run+'/tickets/'+'e'*32+'/reference.html'))
            except BaseException as error:errors.append(error)
        with patch.object(retired_http,'headers',side_effect=held):
            worker=threading.Thread(target=request,daemon=True);worker.start()
            try:
                self.assertTrue(entered.wait(2));pending=self.archive();row=pending['retirement']['attempts'][0]
                self.assertEqual(400,row['headers']['status']);self.assertIsNone(row['write']);self.assertIsNone(row['finallyEpochMs'])
                self.assertNotIn('drained',row);self.assertNotIn('callbackReturned',row)
            finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertEqual([],errors);self.assertEqual(400,values[0][0])
        complete=self.archive();browser_original(complete,pending);row=complete['retirement']['attempts'][0]
        self.assertIsNotNone(row['write']);self.assertIsNotNone(row['finallyEpochMs'])

    def test_actual_late_post_is_denied_and_only_response_metadata_is_retained(self):
        self.client.close();status,body=self.fetch('/runs/'+self.run+'/tickets/'+'e'*32+'/reference.html',
            token='a'*64,method='POST',value={'privateRequestBody':'must-not-be-retained'})
        self.assertEqual(403,status);value=self.archive();row=value['retirement']['attempts'][-1]
        self.assertEqual('POST',row['method']);self.assertEqual(status,row['headers']['status'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),row['headers']['sha256'])
        self.assertNotIn('must-not-be-retained',json.dumps(value));self.assertEqual([],value['responses'])

    def test_missing_audit_clock_or_overflow_is_unavailable_instead_of_empty_success(self):
        self.client.close();retired=self.server.browser_resources.retirements
        for _ in range(MAX_ATTEMPTS):retired.begin(self.run,'e'*32,'reference.html','primary','GET')
        self.assertIsNone(retired.begin(self.run,'e'*32,'reference.html','primary','GET'))
        value=retired.snapshot(self.run);self.assertFalse(value['retirement']['complete']);self.assertEqual(MAX_ATTEMPTS,len(value['retirement']['attempts']))
        with self.assertRaises(NativeUIError):browser_original(value)
    def test_bad_clock_never_suppresses_a_real_late_attempt_as_empty_available_history(self):
        self.client.close();self.server.browser_resources.clock_ms=lambda:False
        self.assertEqual(400,self.fetch('/runs/'+self.run+'/tickets/'+'e'*32+'/reference.html')[0])
        value=self.server.browser_resources.retired_snapshot(self.run)
        self.assertFalse(value['retirement']['complete'])
        with self.assertRaises(NativeUIError):browser_original(value)

    def test_foreign_resource_listener_denials_share_actual_audit_but_not_control_authority(self):
        peer=make_server('r'*64,'a'*64,browser_peer_of=self.server)
        worker=threading.Thread(target=peer.serve_forever,kwargs={'poll_interval':.01},daemon=True);worker.start()
        def stop():
            peer.shutdown();peer.server_close();worker.join(2);self.assertFalse(worker.is_alive())
        self.addCleanup(stop);self.client.close();base=self.base;self.base='http://127.0.0.1:'+str(peer.server_port)+'/feature-fixture/v1'
        self.assertEqual(404,self.fetch('/runs/'+self.run+'/browser-retired',token='r'*64)[0])
        status,_=self.fetch('/runs/'+self.run+'/tickets/'+'e'*32+'/reference.html');self.assertEqual(404,status)
        self.base=base;row=self.archive()['retirement']['attempts'][-1]
        self.assertEqual('foreign',row['origin']);self.assertEqual(404,row['headers']['status'])

    def test_bounded_eviction_never_recreates_an_old_archive_or_reattributes_old_callback(self):
        self.client.close();retired=self.server.browser_resources.retirements;inventory=self.archive()
        token=retired.begin(self.run,'e'*32,'reference.html','primary','GET')
        for index in range(MAX_RUNS):
            run=format(index+1,'032x');retired.close(run,{key:value for key,value in inventory.items() if key!='retirement'}|dict(browserFixtureVersion=1,instance=format(index+1,'032x')))
        with self.assertRaises(KeyError):retired.snapshot(self.run)
        retained=retired.snapshot(format(MAX_RUNS,'032x'));retired.update(token,'headers',dict(status=400,bytes=0,sha256=hashlib.sha256(b'').hexdigest()))
        self.assertEqual(retained,retired.snapshot(format(MAX_RUNS,'032x')))


if __name__=='__main__':unittest.main()
