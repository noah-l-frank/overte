"""Complete tablet v17 public owner with synthetic original target boundaries.

Actual loopback HTTP/inline bytes and receipts drive the common journey. Native
items, DOM events, leases, callbacks and renders are labelled synthetic here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

import test_world_web_feature as world
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.browser_fixture import BrowserResources
from feature_journeys.engine import Journey
from feature_journeys.phase_fixture import PhaseFixtureReader,PhaseRetired
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from overte_phone_tablet_web_feature import PhoneTabletWebFeature
from overte_phone_tablet_web_source import PhoneTabletWebIO
from overte_phone_world_web_source import command,identity
from overte_phone_script_history import pack,unpack
VERSION=world.VERSION
DEVICE=world.DEVICE


class Target(world.Target):
    def __init__(self,*args):
        super().__init__(*args);self.deferred=dict(armed=False,pending=False,held=None,deliveries=[])
        self.tablet_actions=[];self.inline_live=False;self.inline_data=None
    def tablet_web_manager_store(self,_selector):return PrivateFeatureState(self.path/'phone-tablet-web-manager.json')
    def _tablet_web_manager(self,_selector):return Manager(self)
    def _tablet_web_io(self,_selector,**_kwargs):
        return PhoneTabletWebIO(self.send,lambda:self.raw,self.clock.epoch,lambda:self.foreground,123,monotonic=self.clock.now,sleep=self.clock.sleep)
    def _tablet_web_entry(self,_selector,label,*,initial):
        self.tablet_actions.append(label);self.inline_live=False
        if self.fail=='ignored-entry':return
        self.creation+=1
        if label=='WEB TEST':self.load(self.source)
        else:
            with urlopen(self.root+'current',timeout=2) as response:phase=json.load(response)
            url=self.root+'tickets/'+phase['ticket']+'/inline-input.json'
            _status,raw,_response=self.fetch(url);data=json.loads(raw)['dataUrl'];body=base64.b64decode(data.split(',',1)[1],validate=True)
            token=secrets.token_hex(16);transport='http://'+token+'.overte-inline.invalid/index.html'
            self.inline_data=data;self.inline_live=True;self.page+=1
            self.current=dict(url=transport,response=None,text='',focused=False,attempts=[],echoes=[],instance=secrets.token_hex(16),sequence=0,status=0,
                title=re.search(b'<title>([^<]+)</title>',body)[1].decode(),body=body,
                inline=dict(token=token,revision=1,transportUrl=transport,sourceSha256=hashlib.sha256(data.encode()).hexdigest(),
                    bodySha256=hashlib.sha256(body).hexdigest(),bytes=len(body),charset='utf-8',scriptUrl=self.source.rsplit('/',1)[0]+'/injected.js',current=True))
            self.documents.append(dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=transport,finishedEpochMs=self.clock.tick()))
    def _tablet_web_close(self,_selector):
        self.tablet_actions.append('CLOSE');self.inline_live=False
        if self.fail!='cleanup-view-left':self.current=None
    def load(self,url,**kwargs):
        super().load(url,**kwargs);self.current['title']=re.search(b'<title>([^<]+)</title>',self.assert_consumption)[1].decode()
    def dom_packet(self,request):
        value=super().dom_packet(request);value['surface']='tablet';value['source']['dom']['document']['title']=self.current['title']
        if 'inline' in self.current:
            value['source']['nativeView'].update(sourceUrl=self.inline_data,inlineLease=self.inline_live,sourceIdentity='tablet:original-owner')
            value['source']['inline']=deepcopy(self.current['inline']);value['source']['inline']['current']=self.inline_live
        return value
    def input(self,request):
        if request['control']!='bridge':return super().input(request)
        current=self.current
        if self.fail=='ignored-input':return
        ordinal=len(current['attempts'])+1;current['attempts'].append(dict(ordinal=ordinal,capturedEpochMs=self.clock.tick(),eventTimeMs=self.clock.now()*1000))
        packet=dict(contract='overte-web-parity-v1',action='echo',sequence=len(current['echoes'])+1)
        original={key:self.documents[-1][key] for key in ('handle','creation','grant','page','url')}
        if self.deferred['armed'] and 'inline' in current:
            lease=current['inline'];self.deferred.update(armed=False,pending=True,held=dict(original,token=lease['token'],revision=lease['revision'],
                bodySha256=lease['bodySha256'],sourceSha256=lease['sourceSha256'],payloadSha256=hashlib.sha256(json.dumps(packet).encode()).hexdigest(),capturedEpochMs=self.clock.tick(),origin=world.urlsplit(current['url']).scheme+'://'+world.urlsplit(current['url']).netloc,mainFrame=True,payloadBytes=len(json.dumps(packet).encode())))
            return
        primary=world.urlsplit(current['url']).netloc==world.urlsplit(self.root).netloc
        if primary or self.inline_live or self.fail=='foreign-accepted':
            self.requests.append(dict(original,message=json.dumps(packet),capturedEpochMs=self.clock.tick()))
            reply=packet|dict(surface='tablet');self.replies.append(dict(original,message=json.dumps(reply),capturedEpochMs=self.clock.tick()))
            if self.fail!='no-page-receive':current['echoes'].append(dict(sequence=packet['sequence'],surface='tablet',message=json.dumps(reply),receivedEpochMs=self.clock.tick(),observedEpochMs=self.clock.tick()))
    def send(self,request):
        command(request);self.request=deepcopy(request);self.clock.tick();op=request['operation']
        if self.owner is None:
            if op!='reserve':raise NativeUIError('No original lease')
            self.owner=request['ownerToken']
        if self.owner!=request['ownerToken']:raise NativeUIError('Foreign original lease')
        self.sequence+=1
        if op=='reserve':source={'reserved':True}
        elif op=='arm-held':self.deferred['armed']=True;source={'armed':True}
        elif op=='cancel-held':self.deferred['armed']=False;source={'cancelled':True}
        elif op=='deliver-held':
            if not self.deferred['pending']:raise NativeUIError('Original callback absent')
            delivery=self.deferred['held']|dict(deliveredEpochMs=self.clock.tick(),leaseCurrent=self.inline_live,ownerAlive=True,accepted=self.fail=='retired-accepted')
            self.deferred['deliveries'].append(delivery);self.deferred['pending']=False;source={'delivered':True}
        elif op=='retire':
            if self.current or self.deferred['pending'] or self.deferred['armed']:raise NativeUIError('Original browser/callback remains')
            self.retired=True;self.documents=[];self.requests=[];self.replies=[];self.dom_history={}
            self.deferred=dict(armed=False,pending=False,held=None,deliveries=[]);source={'retired':True}
        elif op=='input':
            self.input_count+=1;self.inputs.append(deepcopy(request))
            if self.fail=='lost-input':raise NativeUIError('Lost native return')
            self.input(request);source={'delivered':True}
        else:
            current=self.dom_packet(request['commandId']) if self.current else {}
            if current:self.dom_history[identity(current['source']['nativeView'])]=deepcopy(current)
            source=dict(retired=self.retired,documents=deepcopy(self.documents),requests=deepcopy(self.requests),replies=deepcopy(self.replies),domHistory=deepcopy(self.dom_history),current=current,deferred=deepcopy(self.deferred))
        value=dict(phoneWorldWebVersion=1,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=123,capturedEpochMs=self.clock.tick(),status='ready',source=source)
        if self.status_mutation:self.status_mutation(value)
        self.raw=json.dumps(value)
    def runtime_packet(self,run,url):
        value=super().runtime_packet(run,url)
        for name in ('nativeBefore','nativeAfter'):
            for row in value['source'][name]['views']:row['surface']='tablet'
        if self.current and 'inline' in self.current:
            wanted=hashlib.sha256(self.current['url'].encode()).hexdigest()
            for row in value['source']['java']['views']:row.update(sourceOwned=False,documentOwned=False,sourceSha256=wanted,documentSha256=wanted)
        return value
    def call(self,method,path,body=None):
        result=super().call(method,path,body)
        if self.current and 'inline' in self.current:
            from PIL import Image
            raw=re.findall(b'<img id="feature-marker"[^>]*src="data:image/png;base64,([A-Za-z0-9+/=]+)"',self.current['body']);assert len(raw)==1
            image=Image.open(io.BytesIO(base64.b64decode(result)));image.paste(Image.open(io.BytesIO(base64.b64decode(raw[0]))),(0,0))
            output=io.BytesIO();image.save(output,format='PNG');return base64.b64encode(output.getvalue()).decode()
        return result


class Manager(world.Manager):
    def __init__(self,target):
        super().__init__(target);self.store=target.tablet_web_manager_store('target');self.previous=self.store.read()
        self.state=deepcopy(self.previous) if self.previous else dict(loadAttempted=False,tabletOwned=False,source=None)
    def load_source(self,url):
        _status,raw,_response=self.target.fetch(url)
        if raw!=(world.DEVICE/'fixture/parity/tablet-feature-client.js').read_bytes():raise NativeUIError('Changed ordinary fixture application')
        self.state.update(loadAttempted=True,source=url);self.save();self.target.script=url;self.target.source=url.rsplit('/',1)[0]+'/index.html'


class TabletWebFeatureTests(unittest.TestCase):
    stop=world.WorldWebFeatureTests.stop
    activate=world.WorldWebFeatureTests.activate
    act=world.WorldWebFeatureTests.act
    observe=world.WorldWebFeatureTests.observe
    witness=world.WorldWebFeatureTests.witness
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name);self.path.chmod(0o700)
        self.clock=world.Clock();self.reader,self.actor_token,self.adapter_token=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor_token,adapter_token=self.adapter_token);self.server.journal.clock=self.clock.epoch
        self.server.browser_resources=BrowserResources(clock_ms=self.clock.epoch);self.peer=make_server(self.reader,self.actor_token,browser_peer_of=self.server)
        for server in (self.server,self.peer):
            thread=threading.Thread(target=lambda s=server:s.serve_forever(poll_interval=.01),daemon=True);thread.start();self.addCleanup(self.stop,server,thread)
        self.url=f'http://127.0.0.1:{self.server.server_port}/feature-fixture/v1';self.foreign=f'http://127.0.0.1:{self.peer.server_port}/feature-fixture/v1'
        self.client=Client(self.url,self.reader);self.run,self.fixture_url=self.client.register('tablet-web');self.primary_client=Client(self.url,self.adapter_token)
        self.target=Target(self.clock,self.client,self.foreign,self.path);self.primary=self.flow(self.primary_client,'primary');self.actor=self.flow(Client(self.url,self.actor_token),'actor');self.reports=[]
    def flow(self,client,role):return PhoneTabletWebFeature(self.target,'target',PhaseFixtureReader(client,self.run,'tablet-web',epoch_ms=self.clock.epoch,monotonic=self.clock.now),self.path,self.foreign,role=role,monotonic=self.clock.now,sleep=self.clock.sleep)
    def journey(self):return Journey('tablet-web',self.run,self.fixture_url,
        invoke=lambda operation,call:getattr(self.primary,operation.rsplit('.',1)[1])(call),witness=self.witness,activate=self.client.activate,
        read_artifact=lambda name:(self.path/name).read_bytes(),image_policy={'screen':{'source':'native-screen','marker':[4,4,132,36],'subject':[0,48,160,144]}},
        continuity=lambda *_args:None,monotonic=self.clock.now,epoch_ms=self.clock.epoch,sleep=self.clock.sleep,report=self.reports.append)
    def open_inline(self):
        self.activate();self.observe();self.act('open');self.observe();self.act('open-inline-app',{'resource':'parity-inline-v1'});return self.observe()

    def test_complete_common_v17_tablet_journey_and_original_retirement(self):
        self.journey().execute();self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertEqual(28,len(self.reports[-1]['phases']))
        self.assertIn('INLINE TEST',self.target.tablet_actions);self.assertEqual(1,self.target.backgrounds)
        self.client.close()
        with self.assertRaises(PhaseRetired):self.actor.publish()
        self.primary.finalize();self.primary.finalize();self.assertFalse(any(self.path.glob('phone-tablet-web-*.json')))
    def test_actual_inline_bytes_title_and_lease_are_mandatory(self):
        self.open_inline();self.target.current['inline']['bodySha256']='0'*64
        with self.assertRaises(NativeUIError):self.observe()
    def test_actual_title_cannot_borrow_the_requested_http_document(self):
        self.activate();self.observe();self.act('open');self.target.current['title']='wrong original title'
        with self.assertRaises(NativeUIError):self.observe()
    def test_held_original_send_survives_home_and_is_rejected_by_old_lease(self):
        self.open_inline();self.act('hold-inline-message');value=self.observe()['state'];self.assertEqual((1,1,0),(value['deferredMessages'],value['attemptedMessages'],value['bridgeMessages']))
        held=deepcopy(self.target.deferred['held']);self.act('return-from-inline');self.observe();self.act('deliver-retired-inline-message')
        value=self.observe()['state'];self.assertEqual((0,1,0),(value['deferredMessages'],value['attemptedMessages'],value['bridgeMessages']))
        self.assertEqual(held,{key:self.target.deferred['deliveries'][0][key] for key in held});self.assertFalse(self.target.deferred['deliveries'][0]['leaseCurrent'])
    def test_accepted_retired_callback_cannot_be_a_successful_delivery_receipt(self):
        self.open_inline();self.act('hold-inline-message');self.observe();self.act('return-from-inline');self.observe();self.target.fail='retired-accepted'
        self.act('deliver-retired-inline-message')
        with self.assertRaises(NativeUIError):self.observe()
    def test_foreign_normal_input_stays_separate_from_actual_bridge_admission(self):
        self.activate();self.observe();self.act('open');self.act('navigate-foreign',{'resource':'reference.html'});self.act('foreign-origin-message')
        value=self.observe()['state'];self.assertEqual(('foreign',1,0),(value['origin'],value['attemptedMessages'],value['bridgeMessages']))
    def test_lost_input_is_not_replayed_and_cleanup_delivers_held_only_after_retire(self):
        self.open_inline();self.target.fail='lost-input';ticket=self.activate('hold-inline-message')
        call=dict(contractVersion=world.VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb='hold-inline-message',inputs={})
        before=self.target.input_count
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(before+1,self.target.input_count);self.target.fail=None;self.activate('cleanup');self.primary.cleanup(dict(contractVersion=world.VERSION,runId=self.run));self.assertTrue(self.target.retired)
    def test_original_http_404_requires_actual_reload_after_restoration(self):
        self.activate();self.observe();self.act('open');self.act('navigate',{'resource':'recovery.html'});self.assertEqual(404,self.observe()['state']['httpStatus'])
        self.act('restore-resource');self.assertEqual(404,self.observe()['state']['httpStatus']);self.act('reload');self.assertEqual(200,self.observe()['state']['httpStatus'])

    def test_ordinary_fixture_app_executes_documented_controls_with_real_http_inputs(self):
        self.activate();ticket=self.activate('open-inline-app',{'resource':'parity-inline-v1'})
        # The Script/XHR/Tablet boundaries are synthetic; both actual HTTP
        # response bodies come from the real controlled fixture server.
        script=self.fixture_url+'tickets/'+ticket+'/client.js'
        subprocess.run(['node',str(world.ROOT/'android/phone/tests/tablet-fixture-client-test.js'),
            str(world.DEVICE/'fixture/parity/tablet-feature-client.js'),script],check=True,timeout=10,capture_output=True)

    def retired_journey(self):
        self.journey().execute();self.client.close()
        with self.assertRaises(PhaseRetired):self.actor.publish()

    def test_retirement_plan_rechecks_late_native_or_java_handle_after_source_changed(self):
        self.retired_journey()
        with patch.object(self.primary.retirement_store,'discard',side_effect=OSError('interrupted prune')):
            with self.assertRaises(NativeUIError):self.primary.finalize()
        original=self.target.runtime_packet
        def late_java(run,url):
            value=original(run,url)
            value['source']['java']['views']=[dict(handle='42',creation=1,grant=0,page=0,active=False,destroyed=False,closing=True,
                ownerCurrent=False,foreground=True,loading=False,sourceOwned=False,documentOwned=False,sourceSha256='e'*64,documentSha256='e'*64)]
            return value
        self.target.runtime_packet=late_java
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())
        def late_native(run,url):
            value=original(run,url)
            row=dict(handle='42',surface='tablet',creation=1,grant=0,page=0,sourceOwned=False,documentOwned=False,creationOwned=False,
                sourceSha256='e'*64,documentSha256='e'*64,creationSha256='e'*64,sessionActive=False,authorized=False,created=False,
                pendingCreate=False,retryPending=False,suspended=False,loading=False,callbacks=0,scriptReplies=0,domPending=False)
            for key in ('nativeBefore','nativeAfter'):value['source'][key]['views']=[deepcopy(row)]
            return value
        self.target.runtime_packet=late_native
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())

    def test_completed_plan_reopens_actual_original_png_bytes(self):
        self.retired_journey();record=self.primary.role_store.read();image=unpack(record['payload'])[0]['images'][0]
        self.primary.finalize();(self.path/image['name']).write_bytes(b'changed actual PNG')
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.completed_store.read())

    def test_candidate_replacement_cannot_reuse_owned_inline_grant(self):
        self.open_inline();self.target.binding['artifactSha256']='d'*64
        before=self.target.input_count
        with self.assertRaises(NativeUIError):self.act('submit')
        self.assertEqual(before,self.target.input_count)

    def test_inline_dom_cannot_borrow_a_different_original_fixture_response(self):
        self.open_inline();self.target.current['body']=self.target.current['body'].replace(b'Overte owned inline parity',b'Overte other inline parity')
        data='data:text/html;charset=utf-8;base64,'+base64.b64encode(self.target.current['body']).decode()
        lease=self.target.current['inline'];lease.update(bodySha256=hashlib.sha256(self.target.current['body']).hexdigest(),
            sourceSha256=hashlib.sha256(data.encode()).hexdigest(),bytes=len(self.target.current['body']))
        self.target.inline_data=data
        with self.assertRaises(NativeUIError):self.observe()


if __name__=='__main__':unittest.main()
