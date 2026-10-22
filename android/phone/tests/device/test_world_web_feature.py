"""Public World Web composition on synthetic native/OS/input producers.

Actual loopback HTTP bytes/response IDs and the common v17 journey are used.
The target, trusted DOM events, screenshots and IME delivery are synthetic;
these checks are neither a native build nor device/browser acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.parse import urlsplit
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
DEVICE=ROOT/'tests/device';PHONE=DEVICE/'adapters/android-phone'
sys.path[:0]=[str(DEVICE),str(PHONE)]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.browser_fixture import BrowserResources
from feature_journeys.engine import Journey
from feature_journeys.fixtures import marker_bytes
from feature_journeys.phase_fixture import PhaseFixtureReader,PhaseRetired
from feature_journeys.scenarios import VERSION
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from overte_phone_world_web_feature import PhoneWorldWebFeature
from overte_phone_world_web_source import PhoneWorldWebIO,command,validate,continuity,identity
from overte_phone_world_web_measurements import browser_status,measurement


class Clock:
    def __init__(self):self.value=0.;self.base=int(time.time()*1000)
    def now(self):return self.value
    def epoch(self):return self.base+round(self.value*1000)
    def sleep(self,seconds):self.value+=seconds
    def tick(self):self.value+=.001;return self.epoch()


class Target:
    def __init__(self,clock,client,foreign,path):
        self.clock,self.client,self.foreign,self.path=clock,client,foreign,Path(path)
        self.run=client.run;self.root=client.url+'/runs/'+self.run+'/'
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:456',sessionId='session',generation=1,targetFingerprint='c'*64)
        self.owner=None;self.current=None;self.script=None;self.source=None;self.page=0;self.creation=1
        self.documents=[];self.requests=[];self.replies=[];self.dom_history={};self.history=[];self.known=[]
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1);self.foreground=True;self.retired=False
        self.sequence=0;self.dom_sequence=0;self.native_sequence=0;self.dom_native_sequence=0
        self.request=None;self.fail=None;self.inputs=[];self.backgrounds=0
        self.instance=secrets.token_hex(16);self.dom_native_instance=secrets.token_hex(16);self.runtime_instance=secrets.token_hex(16)
        self.raw=None;self.input_count=0;self.status_mutation=None

    def state_path(self,_selector):return self.path/'session.json'
    def existing_input_session(self,_selector):return nullcontext()
    def existing_session(self,_selector):return self,'session',{'generation':1}
    def world_web_manager_store(self,_selector):return PrivateFeatureState(self.path/'phone-world-web-manager.json')
    def _world_web_manager(self,_selector):return Manager(self)
    def _world_web_clock(self,_selector):return self.clock.epoch()
    def normal_feature_runtime(self,_selector,**_kwargs):
        def observe(_after):return dict(scripts=[] if self.script is None else [dict(url=self.script,path=self.script)],sampleEpochMs=self.clock.tick()),self.clock.epoch()
        return None,observe,deepcopy(self.binding),lambda:self.foreground,None
    def _native_feature_observer(self,_selector,**_kwargs):
        target=self
        class Source:
            def read(self,_after):return dict(instance=target.instance,capturedEpochMs=target.clock.tick(),lifecycle=deepcopy(target.lifecycle))
        return Source()
    def _graphics_lifecycle_status(self,_selector,binding):return dict(foreground=self.foreground,binding=deepcopy(binding))
    def invoke(self,_selector,operation,_values):
        if operation=='lifecycle.background':self.foreground=False;self.lifecycle['backgrounds']+=1;self.backgrounds+=1
        elif operation=='app.launch':
            self.foreground=True;self.lifecycle['activations']+=1
            if self.fail!='old-resume':self.creation+=1;self.load(self.source,history=False)
        else:raise AssertionError(operation)
        return {'performed':True}

    def _world_web_io(self,_selector,**_kwargs):
        return PhoneWorldWebIO(self.send,lambda:self.raw,self.clock.epoch,lambda:self.foreground,123,monotonic=self.clock.now,sleep=self.clock.sleep)
    def send(self,request):
        command(request);self.request=deepcopy(request);self.clock.tick();op=request['operation']
        if self.owner is None:
            if op!='reserve':raise NativeUIError('No original lease')
            self.owner=request['ownerToken']
        if self.owner!=request['ownerToken']:raise NativeUIError('Foreign original lease')
        self.sequence+=1
        if op=='reserve':source={'reserved':True}
        elif op=='retire':
            if self.current is not None:raise NativeUIError('Original view still exists')
            self.retired=True;self.documents=[];self.requests=[];self.replies=[];self.dom_history={};source={'retired':True}
        elif op=='input':
            self.input_count+=1;self.inputs.append(deepcopy(request))
            if self.fail=='lost-input':raise NativeUIError('Lost native return')
            self.input(request);source={'delivered':True}
        else:
            current=self.dom_packet(request['commandId']) if self.current else {}
            if current:self.dom_history[identity(current['source']['nativeView'])]=deepcopy(current)
            source=dict(retired=self.retired,documents=deepcopy(self.documents),requests=deepcopy(self.requests),replies=deepcopy(self.replies),domHistory=deepcopy(self.dom_history),current=current)
        value=dict(phoneWorldWebVersion=1,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=123,capturedEpochMs=self.clock.tick(),status='ready',source=source)
        if self.status_mutation:self.status_mutation(value)
        self.raw=json.dumps(value)

    def fetch(self,url):
        try:response=urlopen(url,timeout=2)
        except HTTPError as error:response=error
        with response:return response.status,response.read(),response.headers['X-Overte-Fixture-Response']
    def load(self,url,*,history=True):
        if self.current and history:self.history.append(self.current['url'])
        status,raw,response=self.fetch(url);self.page+=1
        self.current=dict(url=url,response=response,text='',focused=False,attempts=[],echoes=[],instance=secrets.token_hex(16),sequence=0,status=status)
        row=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=url,finishedEpochMs=self.clock.tick())
        self.documents.append(row)
        if not self.known:self.known=[dict(handle='42',firstObservedEpochMs=self.clock.epoch(),sourceSha256=hashlib.sha256(self.source.encode()).hexdigest())]
        self.assert_consumption=raw
    def dom_packet(self,request):
        self.dom_native_sequence+=1;current=self.current;current['sequence']+=1;epoch=self.clock.tick()
        dom=dict(webDOMVersion=1,requestId=request,instance=current['instance'],sequence=current['sequence'],capturedEpochMs=epoch,
            document=dict(runId=self.run,href=current['url'],responseId=current['response'],readyState='complete'),
            editor=dict(text=current['text'],focused=current['focused']),attempts=deepcopy(current['attempts']),echoes=deepcopy(current['echoes']))
        view=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=current['url'],nativeFinished=True,
            httpErrorStatus=404 if current['status']==404 else 0,inlineLease=False,sourceUrl=self.source,sourceIdentity='original-surface')
        return dict(webNativeVersion=1,commandId=request,runId=self.run,surface='world',instance=self.dom_native_instance,
            sequence=self.dom_native_sequence,processId=123,capturedEpochMs=self.clock.tick(),status='ready',source=dict(nativeView=view,dom=dom))
    def input(self,request):
        current=self.current;control=request['control']
        if self.fail=='ignored-input':return
        if control in ('text','foreign'):
            if control=='text':current.update(text=request['text'],focused=True)
            else:self.foreign_editor=request['text']
        elif control=='bridge':
            epoch=self.clock.tick();ordinal=len(current['attempts'])+1
            current['attempts'].append(dict(ordinal=ordinal,capturedEpochMs=epoch,eventTimeMs=self.clock.now()*1000))
            primary=urlsplit(current['url']).netloc==urlsplit(self.root).netloc
            if primary or self.fail=='foreign-accepted':
                seq=len(current['echoes'])+1;packet=dict(contract='overte-web-parity-v1',action='echo',sequence=seq)
                original={k:self.documents[-1][k] for k in ('handle','creation','grant','page','url')}
                self.requests.append(dict(original,message=json.dumps(packet),capturedEpochMs=self.clock.tick()))
                reply={**packet,'surface':'world'};self.replies.append(dict(original,message=json.dumps(reply),capturedEpochMs=self.clock.tick()))
                if self.fail!='no-page-receive':current['echoes'].append(dict(sequence=seq,surface='world',message=json.dumps(reply),receivedEpochMs=self.clock.tick(),observedEpochMs=self.clock.tick()))
        elif control in ('reference','second','recovery'):
            self.load(current['url'].rsplit('/',1)[0]+'/'+{'reference':'reference.html','second':'page-b.html','recovery':'recovery.html'}[control])
        elif control=='back':self.load(self.history.pop(),history=False)
        elif control=='reload':self.load(current['url'],history=False)
        elif control=='navigate':self.load(self.foreign_editor)
        else:raise AssertionError(control)

    def _web_runtime_observer(self,_selector,**_kwargs):
        target=self
        class Runtime:
            def read(self,run,url):return target.runtime_packet(run,url)
        return Runtime()
    def runtime_packet(self,run,url):
        self.native_sequence+=1;before=self.clock.tick();views=[];java=[]
        if self.current:
            digest=hashlib.sha256(self.source.encode()).hexdigest();document=hashlib.sha256(self.current['url'].encode()).hexdigest()
            identity_row=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,sourceOwned=True,documentOwned=True,sourceSha256=digest,documentSha256=document)
            views=[dict(identity_row,surface='world',creationOwned=True,creationSha256=digest,sessionActive=True,authorized=True,created=True,pendingCreate=False,
                retryPending=False,suspended=False,loading=False,callbacks=0,scriptReplies=0,domPending=False)]
            java=[dict(identity_row,active=True,destroyed=False,closing=False,ownerCurrent=True,foreground=True,loading=False)]
        snap=lambda epoch:dict(capturedEpochMs=epoch,complete=True,knownHandles=deepcopy(self.known),views=deepcopy(views))
        return dict(phoneWebRuntimeVersion=1,commandId=secrets.token_hex(16),runId=run,instance=self.runtime_instance,sequence=self.native_sequence,
            processId=123,capturedEpochMs=self.clock.tick(),status='ready',source=dict(nativeBefore=snap(before),java=dict(javaWebRuntimeVersion=1,
                commandId='placeholder',instance=self.runtime_instance,sequence=self.native_sequence,processId=123,capturedEpochMs=self.clock.epoch(),complete=True,views=java,creations=[]),nativeAfter=snap(self.clock.epoch())))
    def call(self,method,path,body=None):
        if method=='GET' and path.endswith('/screenshot'):
            from PIL import Image,ImageDraw
            ticket=self.client.request('/runs/'+self.run+'/active')['ticket']
            image=Image.new('RGB',(160,144),(128,128,128));image.paste(Image.open(io.BytesIO(marker_bytes(self.run,ticket))),(0,0))
            page=self.current['url'].rsplit('/',1)[-1];color={'page-b.html':'blue','recovery.html':'green'}.get(page,'red')
            if urlsplit(self.current['url']).netloc!=urlsplit(self.root).netloc:color='yellow'
            draw=ImageDraw.Draw(image);draw.rectangle((0,48,159,143),fill=color)
            for x in range(0,160,16):draw.rectangle((x,64,x+5,84),fill='white')
            output=io.BytesIO();image.save(output,format='PNG');return base64.b64encode(output.getvalue()).decode()
        raise AssertionError((method,path,body))


# Correctly correlate the synthetic original Java fence nonce, as the actual JNI
# callback does. This wrapper does not populate any browser state or event count.
_original_runtime=Target.runtime_packet

def _runtime(self,run,url):
    value=_original_runtime(self,run,url)
    value['source']['java']['commandId']=value['commandId'];return value
Target.runtime_packet=_runtime


class Manager:
    def __init__(self,target):
        self.target=target;self.store=target.world_web_manager_store('target');self.previous=self.store.read()
        self.state=deepcopy(self.previous) if self.previous else dict(loadAttempted=False,tabletOwned=False,source=None)
    def save(self):self.store.write(self.state,self.previous);self.previous=deepcopy(self.state)
    def open(self):self.state['tabletOwned']=True;self.save()
    def load_source(self,url):
        self.state.update(loadAttempted=True,source=url);self.save();self.target.script=url
        self.target.source=url.rsplit('/',1)[0]+'/index.html';self.target.load(self.target.source)
    def wait_rows(self,predicate):
        if not predicate([dict(url=self.target.script,path=self.target.script)]):raise NativeUIError('No actual script')
    def close_tablet(self):self.state['tabletOwned']=False;self.save()
    def stop_source(self,url):
        if self.target.fail=='cleanup-view-left':return
        self.target.script=None;self.target.current=None;self.state['loadAttempted']=False;self.save()
    def close(self):
        if self.state['loadAttempted']:raise NativeUIError('Original script remains')
        self.store.discard(self.previous)


class WorldWebFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name);self.path.chmod(0o700)
        self.clock=Clock();self.reader,self.actor_token,self.adapter_token=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor_token,adapter_token=self.adapter_token);self.server.journal.clock=self.clock.epoch
        self.server.browser_resources=BrowserResources(clock_ms=self.clock.epoch)
        self.peer=make_server(self.reader,self.actor_token,browser_peer_of=self.server)
        for server in (self.server,self.peer):
            thread=threading.Thread(target=lambda s=server:s.serve_forever(poll_interval=.01),daemon=True);thread.start();self.addCleanup(self.stop,server,thread)
        self.url=f'http://127.0.0.1:{self.server.server_port}/feature-fixture/v1';self.foreign=f'http://127.0.0.1:{self.peer.server_port}/feature-fixture/v1'
        self.client=Client(self.url,self.reader);self.run,self.fixture_url=self.client.register('world-web')
        self.primary_client=Client(self.url,self.adapter_token)
        self.target=Target(self.clock,self.client,self.foreign,self.path)
        self.primary=self.flow(self.primary_client,'primary');self.actor=self.flow(Client(self.url,self.actor_token),'actor')
        self.reports=[]
    def stop(self,server,thread):server.shutdown();server.server_close();thread.join(timeout=2);self.assertFalse(thread.is_alive())
    def flow(self,client,role):return PhoneWorldWebFeature(self.target,'target',PhaseFixtureReader(client,self.run,'world-web',epoch_ms=self.clock.epoch,monotonic=self.clock.now),
        self.path,self.foreign,role=role,monotonic=self.clock.now,sleep=self.clock.sleep)
    def activate(self,verb='baseline',inputs=None):
        ticket=secrets.token_hex(16);self.client.activate(ticket,verb,inputs or {});return ticket
    def act(self,verb,inputs=None):
        ticket=self.activate(verb,inputs)
        return self.primary.act(dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs or {}))
    def observe(self):return self.primary.observe(dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
    def witness(self):self.actor.publish();return self.client.observe()
    def journey(self):return Journey('world-web',self.run,self.fixture_url,
        invoke=lambda operation,call:getattr(self.primary,operation.rsplit('.',1)[1])(call),witness=self.witness,activate=self.client.activate,
        read_artifact=lambda name:(self.path/name).read_bytes(),image_policy={'screen':{'source':'native-screen','marker':[4,4,132,36],'subject':[0,48,160,144]}},
        continuity=lambda *_args:None,monotonic=self.clock.now,epoch_ms=self.clock.epoch,sleep=self.clock.sleep,report=self.reports.append)

    def test_complete_common_v17_world_web_journey_and_two_role_retirement(self):
        self.journey().execute();self.assertTrue(self.reports[-1]['sequenceCompleted'])
        self.assertEqual(21,len(self.reports[-1]['phases']))
        self.assertGreater(self.target.input_count,12);self.assertEqual(1,self.target.backgrounds)
        self.client.close()
        with self.assertRaises(PhaseRetired):self.actor.publish()
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertFalse(any(self.path.glob('phone-world-web-*.json')))

    def retired_journey(self):
        self.journey().execute();self.client.close()
        with self.assertRaises(PhaseRetired):self.actor.publish()

    def test_resumed_retirement_plan_rechecks_late_original_browser_resources(self):
        self.retired_journey()
        with patch.object(self.primary.retirement_store,'discard',side_effect=OSError('interrupted prune')):
            with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())
        self.target.current=dict(url=self.target.source,response=secrets.token_hex(16),text='',focused=False,
            attempts=[],echoes=[],instance=secrets.token_hex(16),sequence=0,status=200)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())

    def test_retirement_rejects_missing_modified_or_incomplete_original_png_ownership(self):
        from overte_phone_script_history import pack,unpack
        for fault in ('missing','changed','opened','quiet-incomplete'):
            with self.subTest(fault=fault):
                case=WorldWebFeatureTests();case.setUp()
                try:
                    case.retired_journey();store=case.primary.role_store;record=store.read();state=unpack(record['payload'])[0]
                    image=state['images'][0];path=case.path/image['name']
                    if fault=='missing':path.unlink()
                    elif fault=='changed':path.write_bytes(b'changed-original')
                    elif fault=='opened':image.update(phase='opened',sha256=None,bytes=None)
                    else:state['quiet']['complete']=False
                    if fault in ('opened','quiet-incomplete'):store.write(record|dict(payload=pack([state])),record)
                    with case.assertRaises(NativeUIError):case.primary.finalize()
                    case.assertIsNotNone(case.primary.store.read())
                finally:case.doCleanups()

    def test_saved_plan_cannot_hide_a_later_changed_original_png(self):
        from overte_phone_script_history import unpack
        self.retired_journey();record=self.primary.role_store.read();image=unpack(record['payload'])[0]['images'][0]
        with patch.object(self.primary.retirement_store,'discard',side_effect=OSError('interrupted prune')):
            with self.assertRaises(NativeUIError):self.primary.finalize()
        (self.path/image['name']).write_bytes(b'changed after active journal removal')
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())

    def test_lost_input_return_is_never_redelivered(self):
        self.activate();self.observe();self.act('open');self.target.fail='lost-input'
        ticket=self.activate('submit');call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb='submit',inputs={})
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(1,self.target.input_count)

    def test_original_consumed_response_not_requested_status_or_host_ready(self):
        self.activate();self.observe();self.act('open');self.act('navigate',{'resource':'recovery.html'})
        self.assertEqual(404,self.observe()['state']['httpStatus'])
        self.act('restore-resource');self.assertEqual(404,self.observe()['state']['httpStatus'])
        self.act('reload');self.assertEqual(200,self.observe()['state']['httpStatus'])

    def test_missing_page_receive_does_not_borrow_native_reply(self):
        self.activate();self.observe();self.act('open');self.target.fail='no-page-receive';self.act('submit')
        state=self.observe()['state'];self.assertEqual((1,0,1),(state['bridgeMessages'],state['bridgeEchoes'],state['attemptedMessages']))

    def test_foreign_normal_attempt_is_present_and_native_acceptance_stays_independent(self):
        self.activate();self.observe();self.act('open');self.act('navigate-foreign',{'resource':'reference.html'});self.act('foreign-origin-message')
        state=self.observe()['state'];self.assertEqual(('foreign',1,0),(state['origin'],state['attemptedMessages'],state['bridgeMessages']))
        self.target.fail='foreign-accepted';self.act('foreign-origin-message');state=self.observe()['state']
        self.assertEqual((2,1),(state['attemptedMessages'],state['bridgeMessages']))

    def test_truncated_original_native_history_and_foreign_command_are_rejected(self):
        self.activate();self.observe();self.act('open');self.observe()
        self.target.documents=[]
        with self.assertRaises(NativeUIError):self.observe()
        request=deepcopy(self.target.request);request['expectedState']={}
        with self.assertRaises(NativeUIError):command(request)

    def test_cleanup_cannot_retire_a_remaining_original_view(self):
        self.activate();self.observe();self.act('open');self.target.fail='cleanup-view-left';self.activate('cleanup')
        with self.assertRaises(NativeUIError):self.primary.cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertTrue(self.primary.store.read());self.assertFalse(self.target.retired)

    def test_wrong_response_id_or_replaced_receipt_cannot_become_current_document(self):
        self.activate();self.observe();self.act('open');self.observe()
        self.target.current['response']=secrets.token_hex(16)
        with self.assertRaises(NativeUIError):self.observe()

    def test_actor_credentials_cannot_mutate_fixture_or_read_primary_projection(self):
        client=Client(self.url,self.actor_token);self.activate();self.observe()
        with self.assertRaises(ValueError):client.request('/runs/'+self.run+'/browser/control',{'operation':'restore-resource'})
        with self.assertRaises(ValueError):client.request('/runs/'+self.run+'/active',{'ticket':secrets.token_hex(16),'verb':'open','inputs':{}})
        self.actor.publish();self.assertEqual(1,len(self.client.observe()['entries']))


if __name__=='__main__':unittest.main()
