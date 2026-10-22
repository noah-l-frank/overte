"""Mandatory reference-video foundation through the actual Phone public owner.

Native item/IME/media/render boundaries are synthetic. The unchanged parity
HTML/client are fetched from loopback; the common decoder independently checks
encoded frame pixels. No player state/verdict is returned by the adapter.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import threading
import types
import unittest
from urllib.request import urlopen
from unittest.mock import patch

import test_world_web_feature as world
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_web_reference import PhoneWebReference
from overte_phone_world_web_source import command
from self_tests.test_web_video_journey import NativeBoundary,ROI
from web_video_journey import video_journey


class Target(world.Target):
    def __init__(self,clock,url,path,mutation=''):
        super().__init__(clock,types.SimpleNamespace(run='a'*32,url=url+'/feature-fixture/v1'),url,path)
        self.media=NativeBoundary(mutation);self.surface='world';self.tablet_actions=[]
        original_sleep=clock.sleep
        def sleep(seconds):original_sleep(seconds);self.media.sleep(seconds)
        clock.sleep=sleep
    def web_reference_manager_store(self,_selector):return PrivateFeatureState(self.path/'phone-web-reference-manager.json')
    def _web_reference_manager(self,_selector):return Manager(self)
    def _web_reference_tablet(self,_selector,operation):
        self.tablet_actions.append(operation)
        if operation=='open':self.surface='tablet';self.load(self.source)
        else:self.current=None
    def load(self,url,**_kwargs):
        with urlopen(url,timeout=2) as response:raw=response.read()
        if b'id="play"' not in raw:raise NativeUIError('Not the original native reference document')
        self.current=dict(url=url);self.page+=1
        self.documents.append(dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=url,finishedEpochMs=self.clock.tick()))
        if not self.known:self.known=[dict(handle='42',firstObservedEpochMs=self.clock.epoch(),sourceSha256=world.hashlib.sha256(self.source.encode()).hexdigest())]
    def runtime_packet(self,run,url):
        value=super().runtime_packet(run,url)
        for key in ('nativeBefore','nativeAfter'):
            for row in value['source'][key]['views']:row['surface']=self.surface
        return value
    def send(self,request):
        command(request);self.request=deepcopy(request);self.clock.tick();op=request['operation']
        if self.owner is None:
            if op!='reserve':raise NativeUIError('Missing original reference lease')
            self.owner=request['ownerToken'];self.run=request['runId'];self.root=request['fixtureUrl']
        if self.owner!=request['ownerToken']:raise NativeUIError('Foreign original reference lease')
        self.sequence+=1
        if op=='reserve':source={'reserved':True}
        elif op=='retire':
            if self.current:raise NativeUIError('Original reference still active')
            self.retired=True;self.documents=[];source={'retired':True}
        elif op=='input':
            self.input_count+=1;self.inputs.append(deepcopy(request))
            if self.fail=='lost-input':raise NativeUIError('Lost original input return')
            if self.fail!='ignored-input':
                control=request['control'];arguments=dict(surface=request['surface'])
                operation='web.reference.'+({'seekStart':'seek','seek':'seek'}.get(control,control))
                if control in ('seekStart','seek'):arguments['seconds']=0 if control=='seekStart' else 4
                self.media.invoke(operation,arguments)
            source={'delivered':True}
        else:
            current={}
            if self.current:
                current=dict(nativeView=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=self.current['url'],
                    nativeFinished=True,httpErrorStatus=0,inlineLease=False,sourceUrl=self.source,sourceIdentity='original-reference'))
            source=dict(retired=self.retired,documents=deepcopy(self.documents),requests=[],replies=[],domHistory={},current=current)
        self.raw=json.dumps(dict(phoneWorldWebVersion=1,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=123,capturedEpochMs=self.clock.tick(),status='ready',source=source))


class Manager(world.Manager):
    def __init__(self,target):
        self.target=target;self.store=target.web_reference_manager_store('target');self.previous=self.store.read()
        self.state=deepcopy(self.previous) if self.previous else dict(loadAttempted=False,tabletOwned=False,source=None)
    def load_source(self,url):
        with urlopen(url,timeout=2) as response:source=response.read()
        if source!=(world.DEVICE/'fixture/parity/client.js').read_bytes():raise NativeUIError('Changed original fixture input')
        super().load_source(url)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*_args):pass


class WebReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name);self.path.chmod(0o700)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(world.DEVICE/'fixture')))
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def target(self,mutation=''):
        clock=world.Clock();target=Target(clock,self.url,self.path,mutation);owner=PhoneWebReference(target,'target',monotonic=clock.now,sleep=clock.sleep)
        return clock,target,owner
    def journey(self,clock,target,owner,surface='world'):
        return video_journey(surface,self.url+'/parity/client.js',ROI,invoke=owner.invoke,capture=target.media.capture,
            retain=target.media.retain,assert_session=target.media.assert_session,monotonic=clock.now,sleep=clock.sleep,report=target.media.reports.append)

    def test_complete_common_video_sequence_uses_native_controls_on_both_surfaces(self):
        for surface in ('world','tablet'):
            with self.subTest(surface=surface):
                clock,target,owner=self.target();result=self.journey(clock,target,owner,surface)
                self.assertTrue(result['observations']['resume']['movingReferenceVideoPixelsObserved'])
                self.assertEqual(['play','pause','seek','play'],[request['control'] for request in target.inputs])
                self.assertIsNone(owner.store.read());self.assertIsNone(target.web_reference_manager_store('target').read());self.assertTrue(target.retired)
                if surface=='tablet':self.assertEqual(['open','close'],target.tablet_actions)
                self.assertEqual({'performed':True},owner.invoke('web.reference.close',{'surface':surface}))
                owner.cleanup();self.assertIsNone(owner.completed.read())
    def test_ack_or_surrounding_ui_motion_cannot_pass_frozen_video(self):
        clock,target,owner=self.target('frozen')
        with self.assertRaisesRegex(AssertionError,'moving encoded'):self.journey(clock,target,owner)
        self.assertTrue(target.media.reports[-1]['normalCloseSucceeded']);self.assertIsNone(owner.store.read())
    def test_acknowledged_pause_and_seek_must_change_original_encoded_pixels(self):
        for mutation in ('pause-ignored','seek-ignored','resume-ignored'):
            with self.subTest(mutation=mutation):
                clock,target,owner=self.target(mutation)
                with self.assertRaises(AssertionError):self.journey(clock,target,owner)
                self.assertFalse(target.media.reports[-1]['controlSequenceCompleted']);self.assertIsNone(owner.store.read())
    def test_lost_pointer_return_cannot_replay_a_play_input(self):
        clock,target,owner=self.target();owner.invoke('web.reference.open',{'surface':'world','scriptUrl':self.url+'/parity/client.js'})
        target.fail='lost-input'
        for _ in range(2):
            with self.assertRaises(NativeUIError):owner.invoke('web.reference.play',{'surface':'world'})
        self.assertEqual(1,target.input_count)
        target.fail=None;owner.cleanup();self.assertTrue(target.retired)
    def test_candidate_change_and_remaining_browser_refuse_input_or_retirement(self):
        clock,target,owner=self.target();owner.invoke('web.reference.open',{'surface':'world','scriptUrl':self.url+'/parity/client.js'})
        original=deepcopy(target.binding);target.binding['artifactSha256']='f'*64
        with self.assertRaises(NativeUIError):owner.invoke('web.reference.play',{'surface':'world'})
        self.assertEqual(0,target.input_count);target.binding=original;target.fail='cleanup-view-left'
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertIsNotNone(owner.store.read());self.assertFalse(target.retired)
    def test_reference_native_grammar_cannot_borrow_feature_fixture_or_script_eval(self):
        clock,target,owner=self.target();owner.invoke('web.reference.open',{'surface':'world','scriptUrl':self.url+'/parity/client.js'})
        request=target.request
        for changes in ({'fixtureUrl':self.url+'/other/'},{'javascript':'x.click()'},{'surface':'foreign'},{'expectedFrame':48}):
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):command(request|changes)
        owner.cleanup()

    def test_active_java_owner_must_be_ready_before_open_or_media_input(self):
        clock,target,owner=self.target();arguments={'surface':'world','scriptUrl':self.url+'/parity/client.js'}
        owner.invoke('web.reference.open',arguments);original=target.runtime_packet
        def stale_java(run,url):
            value=original(run,url)
            for row in value['source']['java']['views']:row['ownerCurrent']=False
            return value
        target.runtime_packet=stale_java
        for operation,args in (('web.reference.open',arguments),('web.reference.play',{'surface':'world'})):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):owner.invoke(operation,args)
        self.assertEqual(0,target.input_count);target.runtime_packet=original;owner.cleanup()

    def test_double_close_reacquires_late_original_browser_absence(self):
        clock,target,owner=self.target();owner.invoke('web.reference.open',{'surface':'world','scriptUrl':self.url+'/parity/client.js'})
        owner.invoke('web.reference.close',{'surface':'world'});self.assertIsNotNone(owner.completed.read())
        target.load(target.source)
        with self.assertRaises(NativeUIError):owner.invoke('web.reference.close',{'surface':'world'})
        self.assertIsNotNone(owner.completed.read())


if __name__=='__main__':unittest.main()
