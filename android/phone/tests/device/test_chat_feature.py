"""Public Chat/common replay at explicit synthetic native/Qt/network seams.

Actual private CAS/FD files, TokenChatUI/PhoneChatIO, all strict native readers,
real loopback phase/actor HTTP and the common Journey execute. No Agent, mixer,
Phone, Appium server or device executes; source producers below are synthetic.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
from types import SimpleNamespace
import base64
import hashlib
import io
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'android/phone/tests/device')]
from PIL import Image,ImageDraw
from adapters.chat_actor_files import ChatActorFiles,SOURCE,COMMAND,RESULT,encode,stamp,node
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_chat_observation import NativeChatObservation,ChatCaptureOwner,OwnedChatCapture
from adapters.native_chat_view import NativeChatView
from adapters.native_chat_history import NativeChatHistory
from adapters.native_chat_peer import NativeChatPeer
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_roots import NativeScriptRoots
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_phone_touch_state import NativePhoneTouchState
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError,W3C_ELEMENT
from adapters.token_chat_ui import TokenChatUI
from feature_journeys.engine import Journey
from feature_journeys.phase_fixture import PhaseFixtureReader,PhaseRetired,PhasePending
from feature_journeys.scenarios import VERSION
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.fixtures import context
from overte_phone_chat_feature import PhoneChatFeature
from overte_phone_chat_peer import PhoneChatPeer
from fixture.domain import DomainControlHandler
from overte_phone_chat_controls import PhoneChatIO
from overte_phone_chat_measurements import source_pins
from overte_phone_script_history import unpack
from chat_native_boundary import ChatNativeBoundary
from self_tests.test_chat_actor_files import FileActor
from self_tests.test_native_chat_observation import Boundary as ReceiveBoundary
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_avatar_render import avatar_source
with patch.dict(os.environ,OVERTE_DEVICE_ADAPTER_MANIFEST=str(ROOT/'tests/device/adapters/mock/adapter.json'),OVERTE_DEVICE_TARGET_SELECTOR='synthetic-chat',OVERTE_DEVICE_ARTIFACT_DIR='/tmp'):
    from overte_session import OverteSession


class Clock:
    def __init__(self):self.value=0.;self.base=int(time.time()*1000)
    def now(self):return self.value
    def epoch(self):return self.base+round(self.value*1000)


class Receiver(ReceiveBoundary):
    def __init__(self,target,peer=False):super().__init__();self.target=target;self.peer=peer
    def send(self,request):
        super().send(request);t=self.target;source=self.value['source']
        self.value.update(instance=('c' if self.peer else 'b')*32,processId=32 if self.peer else 31,capturedEpochMs=t.epoch())
        if self.present and self.opened==20000:self.opened=t.epoch()
        source.update(selfSha256=('d' if self.peer else 'e')*64,mixerPresent=t.online,mixerSha256=t.mixer_sha if t.online else '',
                      openedEpochMs=self.opened if self.present else 0,events=deepcopy(self.events))
    def event(self,text,channel,sender,local=False):
        if self.present and not self.retired:self.events.append(dict(sequence=len(self.events)+1,capturedEpochMs=self.target.epoch(),senderSha256=sender,localOnly=local,channel=channel,text=text))


class PeerControl:
    def __init__(self,t):
        self.target=t;self.value=None;self.sequence=0;self.used=set()
        self.source=dict(selfSha256='d'*64,mixerPresent=True,mixerSha256=t.mixer_sha,leasePresent=False,admitted=False,restored=False,
            position=dict(x=2.,y=0.,z=2.),originalPosition={},inputSequence=0,lastInput={},handback={})
    def send(self,request):
        self.sequence+=1;t=self.target;s=self.source;operation=request['operation']
        s.update(mixerPresent=t.online,mixerSha256=t.mixer_sha if t.online else '')
        if operation=='lease':s.update(leasePresent=True,admitted=True,originalPosition=deepcopy(s['position']))
        elif operation.startswith('send-'):
            if operation in self.used:return
            self.used.add(operation);s['position']=deepcopy(s['originalPosition'])
            if operation.endswith('distant'):s['position']['x']+=128
            text=('hidden-' if operation.endswith(('hidden','distant')) else 'reply-')+t.run
            channel='local' if operation.startswith('send-local-') else 'domain'
            s['inputSequence']+=1;s['lastInput']=dict(sequence=s['inputSequence'],operation=operation,capturedEpochMs=t.epoch(),position=deepcopy(s['position']),payloadSha256=hashlib.sha256(encode(dict(text=text,channel=channel,position=s['position']))).hexdigest())
            if t.fault!='peer-send-ack-only':t.deliver(text,channel,'peer')
        elif operation=='restore' and not s['restored']:
            if t.fault!='ignore-peer-restore':s.update(position=deepcopy(s['originalPosition']),restored=True,leasePresent=False,
                handback=dict(capturedEpochMs=t.epoch(),position=deepcopy(s['originalPosition']),inputSequence=s['inputSequence']))
        self.value=dict(chatPeerVersion=1,**{k:request[k] for k in ('commandId','runId','operation')},instance='c'*32,sequence=self.sequence,
            processId=32,capturedEpochMs=t.epoch(),source=deepcopy(s))


class Actor(FileActor):
    def __init__(self,root,t):super().__init__(root);self.target=t;self.receiver=t.secondary;self.peer=t.peer_control;self.native=self.receiver
    def tick(self):
        path=self.root/COMMAND
        if path.exists():self.native=self.peer if json.loads(path.read_bytes())['action']=='feature-chat-peer' else self.receiver
        super().tick()
    def released(self,identity):
        if node(os.fstat(self.source_fd))==identity:return False
        if self.release and self.receiver.retired and not (self.root/RESULT).exists():self.close()
        return self.fd<0 or node(os.fstat(self.fd))!=identity


class Target:
    def __init__(self,root,clock,run):
        self.root,self.clock,self.run=root,clock,run;self.fault='';self.online=True;self.mixer_generation=1;self.mixer_sha='f'*64
        self.binding=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:19',sessionId='owned-phone',generation=1,targetFingerprint='3'*64)
        self.peer_binding=dict(self.binding,artifactSha256='4'*64,processIdentity='32:20',sessionId='owned-ac',targetFingerprint='5'*64)
        self.running=True;self.foreground=True;self.backgrounds=0;self.activations=1;self.native_sequence=0;self.avatar_sequence=0;self.view_sequence=0;self.touch_sequence=0;self.touch_held=False
        self.config_sha='6'*64;self.history_kind='unset';self.saved=[];self.history_sequence=0;self.history_source=None
        self.primary=Receiver(self);self.secondary=Receiver(self,True);self.peer_control=PeerControl(self)
        self.widgets=ChatNativeBoundary();self.widgets.ui.panel=False;self.widgets.ui.tablet=False
        self.widgets.ui.monotonic=clock.now;self.widgets.ui.sleep=self.sleep;self.widgets.native.sleep=self.sleep
        original=self.widgets.ui.input
        def input(identifier,action,reference,value=None):
            draft=self.widgets.ui.draft;channel=self.widgets.ui.channel
            original(identifier,action,reference,value)
            if identifier=='chat.erase' and self.fault!='erase-ack-only':self.saved=[];self.history_kind='null'
            if identifier=='chat.send' or identifier=='chat.input' and action=='submit':
                if self.fault!='send-ack-only':self.deliver(draft,channel,'primary')
            if self.fault=='lost-focus-ack' and identifier=='chat.input' and action=='activate':self.fault='';raise NativeUIError('Lost synthetic focus reply')
            if self.fault=='lost-send-ack' and identifier=='chat.send':self.fault='';raise NativeUIError('Lost synthetic input reply')
        self.widgets.ui.input=input
        self.widgets.mutate=lambda packet:packet.update(capturedEpochMs=self.epoch()) if packet.get('action')=='observe' else None
        self.native_ui=NativeUI(self,'owned-phone',self.guard,monotonic=clock.now,sleep=self.sleep)
        self.actor_root=root/'native-actor';self.actor_root.mkdir(mode=0o700)
        self.script_bytes=(ROOT/'scripts/communityScripts/armored-chat/armored_chat.js').read_bytes()
        self.script_sha=hashlib.sha256((ROOT/'tests/device/fixture/domain_peer_agent.js').read_bytes()).hexdigest()
        source=dict(actorVersion=1,instance='c'*32,processId=32,configuredEpochMs=self.epoch()-100,scriptSha256=self.script_sha)
        (self.actor_root/SOURCE).write_bytes(encode(source));(self.actor_root/SOURCE).chmod(0o600)
        self.actor=Actor(self.actor_root,self);self.script_sequence=0;self.root_sequence=0
        self.actor_enabled=False;self.actor_busy=False;self.actor_finished=False;self.actor_flow=None;self.primary_flow=None
        class Control(DomainControlHandler):
            token='control-token-'+('x'*64)
            mixer=staticmethod(self.mixer_transition)
            def log_message(self,*_args):pass
        self.mixer_server=ThreadingHTTPServer(('127.0.0.1',0),Control)
        self.mixer_thread=threading.Thread(target=lambda:self.mixer_server.serve_forever(poll_interval=.01),daemon=True);self.mixer_thread.start()
        actor_config=root/'actor-config.json';ready=root/'domain-ready.json'
        PrivateFeatureState(actor_config).write(dict(actorFilesVersion=1,directory=str(self.actor_root),expectedScriptSha256=self.script_sha,
            expectedExecutableSha256='4'*64,ownerToken='a'*64,configHome=str(root)),None)
        PrivateFeatureState(ready).write(dict(controlToken=Control.token,messagesMixerControlUrl=f'http://127.0.0.1:{self.mixer_server.server_port}/v1/messages-mixer-state'),None)
        self.config=dict(chatFeatureVersion=1,artifactRoot=str(root),peer=dict(chatPeerFixtureVersion=1,actorConfiguration=str(actor_config),domainReady=str(ready),
            actorArtifact=dict(sourceRevision=self.binding['sourceRevision'],artifactSha256='4'*64)))
    def epoch(self):return self.clock.epoch()
    def options(self):return dict(monotonic=self.clock.now,sleep=self.sleep)
    def guard(self):return self.running
    def state_path(self,_selector):return self.root/'session.json'
    def normal_feature_runtime(self,_selector,*,read_only=False):return self.native_ui,None,deepcopy(self.binding),self.guard,None
    @contextmanager
    def existing_input_session(self,_selector):yield
    def sleep(self,value):
        self.actor.tick()
        self.clock.value+=value;self.widgets.ui.elapsed=100+round(self.clock.value*1000)
        if self.actor_enabled and not self.actor_busy and not self.actor_finished:
            import fcntl
            fd=os.open(self.root/'phone-script-sources.lock',os.O_RDWR|os.O_CREAT,0o600)
            try:
                try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                fcntl.flock(fd,fcntl.LOCK_UN)
            finally:os.close(fd)
            self.actor_busy=True
            try:self.actor_flow().publish()
            except PhaseRetired:self.actor_flow().retire_actor();self.actor_finished=True
            except PhasePending:pass
            finally:self.actor_busy=False
    def detach(self):
        self.actor.close_all();self.mixer_server.shutdown();self.mixer_server.server_close();self.mixer_thread.join(timeout=2)
    def mixer_transition(self,action=None):
        if action is not None:
            if self.fault!='mixer-ack-only':self.online=action=='online'
            self.mixer_generation+=1
            if self.online and self.fault!='cached-mixer':self.mixer_sha=hashlib.sha256(str(self.mixer_generation).encode()).hexdigest()
        return dict(mixerProcessVersion=1,running=self.online,generation=self.mixer_generation,pending=False)
    def deliver(self,text,channel,sender):
        # Explicit synthetic wire and original-script consumer, separate from
        # input ACKs. Offline primary sends emit actual localOnly only.
        sender_sha='e'*64 if sender=='primary' else 'd'*64
        if self.online:
            self.primary.event(text,channel,sender_sha);self.secondary.event(text,channel,sender_sha)
        elif sender=='primary':self.primary.event(text,channel,sender_sha,True)
        else:return
        position=dict(x=0.,y=0.,z=0.) if sender=='primary' else self.peer_control.source['position']
        if channel=='local' and math_distance(position)>20:return
        self.saved.append(dict(channel=channel,text=text,timestamp=self.epoch()));self.history_kind='array'
        (self.widgets.ui.local if channel=='local' else self.widgets.ui.domain).append(text)
    def call(self,method,path,body=None):
        if path.endswith('/screenshot'):
            image=Image.new('RGB',(320,240),'#345678');draw=ImageDraw.Draw(image)
            for index in range(30):draw.rectangle((index*11,60+(index%3)*30,index*11+5,200),fill=('white' if index%2 else 'black'))
            draw.text((10,10),self.widgets.ui.channel+' '+str(self.view_sequence),fill='white');draw.text((10,30),self.widgets.ui.draft,fill='white');out=io.BytesIO();image.save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()
        if path.endswith('/elements'):
            identifier=body['value'].split(':id/')[-1]
            visible=self.widgets.ui.tablet if identifier=='nav.close' else not self.widgets.ui.tablet if identifier=='tablet.open' else False
            return [{W3C_ELEMENT:identifier}] if visible else []
        if '/element/' in path:
            identifier=path.split('/element/')[1].split('/')[0]
            if path.endswith('/displayed'):return self.widgets.ui.tablet if identifier=='nav.close' else not self.widgets.ui.tablet
            if path.endswith('/enabled'):return True
            if path.endswith('/click'):
                self.widgets.ui.tablet=identifier=='tablet.open';return None
        if path.endswith('/actions'):return None
        raise AssertionError((method,path,body))
    def existing_session(self,_selector):return self,'owned-phone',{}
    def _world_web_clock(self,_selector):return self.epoch()
    def invoke(self,_selector,operation,_values):
        if operation=='lifecycle.background':self.foreground=False;self.backgrounds+=1;self.widgets.ui.focus=False;self.widgets.ui.keyboard_request=False;return {'backgrounded':True}
        if operation=='app.launch':self.foreground=True;self.activations+=1;return {'launched':True}
        raise AssertionError(operation)
    def _graphics_lifecycle_status(self,*_args):return dict(foreground=self.foreground)
    def chat_capture_store(self,_selector):return PrivateFeatureState(self.root/'phone-chat-capture-owner.json')
    def _chat_receive(self,_selector,*,read_only=True):return NativeChatObservation(self.primary.send,self.primary.read,self.epoch,self.guard,31,**self.options())
    def _chat_capture(self,selector,run):return OwnedChatCapture(self._chat_receive(selector),ChatCaptureOwner(self.chat_capture_store(selector),self.binding,self.guard),run)
    def _chat_controls(self,_selector,intent,run,*,read_only=False):
        io=PhoneChatIO(self.widgets.send,lambda:json.dumps(self.widgets.value),self.epoch,self.guard,31,tablet_shown=lambda:self.widgets.ui.tablet,**self.options())
        return TokenChatUI(io,intent,run,**self.options())
    def _chat_view(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.view_sequence+=1;w=self.widgets.ui
            source=dict(tabletShown=w.tablet,editorFocused=w.focus,editorHasDraft=bool(w.draft),keyboard=dict(available=True,backend='native-touch-metrics',visible=w.keyboard_request),
                ui=dict(present=False),storage=dict(kind=self.history_kind,count=len(self.saved),unowned=0,events=deepcopy(self.saved),configSha256=self.config_sha))
            if w.panel:source['ui']=dict(present=True,generation='a'*32,channel=w.channel,draft=w.draft,keyboardRequested=w.keyboard_request,localMessages=deepcopy(w.local),domainMessages=deepcopy(w.domain),localRowCount=len(w.local),domainRowCount=len(w.domain),visibleMessages=deepcopy(w.local if w.channel=='local' else w.domain),visibleRowCount=len(w.local if w.channel=='local' else w.domain))
            value=dict(chatViewVersion=1,commandId=command['commandId'],runId=command['runId'],instance='7'*32,sequence=self.view_sequence,processId=31,capturedEpochMs=self.epoch(),source=source)
            if self.fault=='view-counter':value['sequence']=1
            if self.fault=='no-keyboard-source':value['source']['keyboard']={'available':False}
        return NativeChatView(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())
    def _chat_history(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.history_sequence+=1;operation=command['operation']
            if self.history_source is None:self.history_source=dict(scopePresent=False,retired=False,restored=False,originalKind='',originalSha256='',currentSha256='8'*64,configSha256='9'*64,openedEpochMs=0,handbackEpochMs=0,closed=True)
            source=self.history_source
            if operation=='capture':source.update(scopePresent=True,originalKind=self.history_kind,originalSha256='8'*64,openedEpochMs=self.epoch())
            elif operation=='restore' and self.fault!='history-restore-ack':source.update(restored=True,handbackEpochMs=self.epoch(),currentSha256='8'*64);self.history_kind=source['originalKind']
            elif operation=='retire':source.update(retired=True,scopePresent=False)
            source['closed']=not self.widgets.ui.panel and not self.widgets.ui.focus and not self.widgets.ui.keyboard_request
            value=dict(chatHistoryVersion=1,**{k:command[k] for k in ('commandId','runId','operation')},instance='a'*32,sequence=self.history_sequence,processId=31,capturedEpochMs=self.epoch(),source=deepcopy(source))
        return NativeChatHistory(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())
    def _chat_peer(self,_selector,run,config,*,read_only=True,attach_files=True):
        # Only Linux process/start/executable qualification is substituted here.
        # Actual private actor FD files, normal reader factories and the original
        # domain HTTP handler/controller-client execute unchanged.
        def qualify(pid,directory,executable,owned):
            assert pid==32 and directory==self.actor_root and executable=='4'*64
            return SimpleNamespace(pid=32,process_identity='32:20',guard=self.guard,released=self.actor.released,close=lambda:None)
        with patch('overte_phone_chat_peer.LinuxChatActorProcess',side_effect=qualify):
            return PhoneChatPeer(config,self.state_path(_selector),self.binding,run,read_only=read_only,attach_files=attach_files,
                script_sha256=source_pins()['peer']['utf8Sha256'],clock_ms=self.epoch,**self.options())
    def _native_feature_observer(self,_selector,*,read_only=True):
        source=FeatureBoundary()
        def send(request):
            source.send(request);self.native_sequence+=1
            source.sample.update(instance='b'*32,sequence=self.native_sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),lifecycle=dict(backgrounds=self.backgrounds,activations=self.activations,launches=1))
            source.sample.pop('animationFence',None);source.sample['animation']['capturedEpochMs']=self.epoch();source.sample['animation']['clip']['evaluatedEpochMs']=self.epoch()
        return NativeFeatureObservation(send,source.original,self.epoch,self.guard,31,**self.options())
    def _avatar_render_observer(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.avatar_sequence+=1;source=avatar_source();source['pose']['feetPosition']=[0,0,0]
            value=dict(schemaVersion=1,requestId=command['commandId'],instance='c'*32,sequence=self.avatar_sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)
        return NativeAvatarRender(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())
    def _touch_state_observer(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.touch_sequence+=1
            source=dict(phoneTouchStateVersion=1,pluginActive=True,eventPointCount=int(self.touch_held),moveContact=self.touch_held,viewContact=False,
                buttonContacts=0,unusedContacts=0,axes=[],pressedButtons=[],pendingPinchIn=0.,pendingPinchOut=0.,lastPinchScale=0.)
            value=dict(schemaVersion=1,requestId=command['commandId'],instance='d'*32,sequence=self.touch_sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)
        return NativePhoneTouchState(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())
    def _script_roots(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.root_sequence+=1;value=dict(scriptRootsVersion=1,commandId=command['commandId'],instance='d'*32,sequence=self.root_sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=dict(defaultScriptsUrl='file:///actual/scripts/'))
        return NativeScriptRoots(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())
    def _script_execution_observer(self,_selector,*,read_only=True):
        value=None
        def send(command):
            nonlocal value
            self.script_sequence+=1;url='file:///actual/scripts/communityScripts/armored-chat/armored_chat.js';actual=self.script_bytes.decode('utf-8').encode('utf-16le');pin=dict(codeUnits=len(actual)//2,sha256=hashlib.sha256(actual).hexdigest())
            engine=dict(url=url,running=True,stopping=False,finished=False,required=dict(instance='e'*32,sequence=0,modules=[]),
                code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=pin['codeUnits'],sha256=pin['sha256'],submittedEpochMs=self.clock.base-1000),
                compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=42,resourceName=url,encoding='utf-16le-code-units',codeUnits=pin['codeUnits'],sha256=pin['sha256'],compiledEpochMs=self.clock.base-1000)]))
            source=dict(complete=True,engines=[engine],sourceIdentityVersion=1,compiledSourceVersion=1,effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]),
                loadSourceVersion=1,loads=dict(complete=True,instance='f'*32,sequence=0,events=[]),membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[dict(instance='e'*32,assigned=True,url=url,loadGeneration=1,assignedEpochMs=self.clock.base-1000)]))
            if self.fault=='compiled-code':source['engines'][0]['compiled']['compilations'][0]['sha256']='0'*64
            value=dict(schemaVersion=1,requestId=command['commandId'],instance='a'*32,sequence=self.script_sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)
        return NativeScriptObservation(send,lambda:json.dumps(value),self.epoch,self.guard,31,**self.options())


def math_distance(position):return sum(position[k]**2 for k in 'xyz')**.5


class ChatFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.clock=Clock();self.server=make_server('r'*64,'a'*64,adapter_token='d'*64);self.server.journal.clock=self.clock.epoch
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.url=f'http://127.0.0.1:{self.server.server_port}/feature-fixture/v1';self.client=Client(self.url,'r'*64)
        self.run,self.fixture_url=self.client.register('chat');self.target=Target(self.root,self.clock,self.run);self.addCleanup(self.target.detach)
        self.primary_client=AdapterFixtureClient(self.url,'d'*64);self.actor_client=Client(self.url,'a'*64)
        self.target.primary_flow=lambda:self.flow();self.target.actor_flow=lambda:self.flow('actor');self.reports=[]
        self.activate()
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def flow(self,role='primary'):
        client=self.primary_client if role=='primary' else self.actor_client
        return PhoneChatFeature(self.target,'controlled',PhaseFixtureReader(client,self.run,'chat',epoch_ms=self.clock.epoch,monotonic=self.clock.now),self.target.config,role=role,**self.target.options())
    def activate(self,verb='baseline',inputs=None):
        ticket=uuid.uuid4().hex;self.client.activate(ticket,verb,inputs or {});return ticket
    def act(self,verb,inputs=None):
        ticket=self.activate(verb,inputs);call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs or {})
        self.flow().act(call);return call
    def observe(self):return self.flow().observe(dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
    def witness(self):self.flow('actor').publish();return self.client.observe()
    def journey(self):
        session=object.__new__(OverteSession);session._invoke=lambda operation,fields:getattr(self.flow(),operation.rsplit('.',1)[1])(fields)
        return Journey('chat',self.run,self.fixture_url,invoke=lambda operation,fields:session.feature_operation('chat',operation.rsplit('.',1)[1],fields),
            witness=self.witness,activate=self.client.activate,read_artifact=lambda name:(self.root/name).read_bytes(),image_policy={},continuity=lambda *_:None,
            monotonic=self.clock.now,epoch_ms=self.clock.epoch,sleep=self.target.sleep,report=self.reports.append)
    def seed_domain_message(self):
        self.observe();self.act('open');self.act('select-channel',dict(channel='domain'));self.act('type',dict(text=context(self.run)['unicode']))
    def cleanup_now(self):
        self.activate('cleanup');return self.flow().cleanup(dict(contractVersion=VERSION,runId=self.run))
    def retire_now(self):
        self.cleanup_now();self.flow('actor').publish();self.client.close();self.flow('actor').retire_actor()
    def test_input_ack_without_original_storage_and_peer_delivery_never_succeeds(self):
        self.seed_domain_message();self.target.fault='send-ack-only'
        with self.assertRaises(NativeUIError):self.act('send')
        self.assertEqual([],self.target.saved);self.assertEqual([],self.target.secondary.events)
        self.assertIsNotNone(self.flow().store.read())
    def test_peer_send_ack_without_primary_native_receive_is_red(self):
        self.observe();self.act('open');self.target.fault='peer-send-ack-only'
        with self.assertRaises(NativeUIError):self.act('peer-send',dict(text=context(self.run)['reply'],channel='domain'))
        self.assertEqual([],self.target.saved);self.assertEqual([],self.target.primary.events)
        self.assertEqual(1,self.target.peer_control.source['inputSequence']);self.assertIsNotNone(self.flow().store.read())
    def test_lost_applied_send_reply_resumes_from_originals_without_sending_twice(self):
        self.seed_domain_message();ticket=self.activate('send');call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb='send',inputs={})
        self.target.fault='lost-send-ack'
        with self.assertRaises(NativeUIError):self.flow().act(call)
        self.assertEqual(1,len(self.target.secondary.events));self.flow().act(call)
        self.assertEqual(1,len(self.target.secondary.events));self.assertEqual(1,sum(row['controlId']=='chat.send' for row in self.target.widgets.input_requests))
        self.assertEqual([context(self.run)['unicode']],self.observe()['state']['peerMessages'])
    def test_partial_type_focus_reply_loss_resumes_absolute_editor_input_without_send(self):
        self.observe();self.act('open');ticket=self.activate('type',dict(text=context(self.run)['unicode']))
        call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb='type',inputs=dict(text=context(self.run)['unicode']))
        self.target.fault='lost-focus-ack'
        with self.assertRaises(NativeUIError):self.flow().act(call)
        self.assertEqual('',self.target.widgets.ui.draft);self.assertTrue(self.target.widgets.ui.focus)
        self.flow().act(call);self.assertEqual(context(self.run)['unicode'],self.observe()['state']['draft'])
        self.assertEqual([],self.target.primary.events);self.assertEqual([],self.target.secondary.events)

    def test_cancelled_partial_acquisition_preserves_authority_until_sources_recover_then_retires(self):
        self.target.fault='compiled-code'
        with self.assertRaises(NativeUIError):self.observe()
        self.assertIsNotNone(self.flow().store.read());self.assertTrue(self.target.peer_control.source['leasePresent'])
        with self.assertRaises(NativeUIError):self.cleanup_now()
        self.assertIsNotNone(self.flow().store.read());self.assertFalse(self.target.widgets.input_requests)
        self.target.fault='';self.retire_now();self.assertTrue(self.flow().finalize());self.assertEqual('unset',self.target.history_kind)
        self.assertFalse(self.target.peer_control.source['leasePresent']);self.assertIsNone(self.flow().store.read())

    def test_missing_native_keyboard_actual_touch_or_compiled_source_prevents_baseline(self):
        for fault in ('no-keyboard-source','compiled-code'):
            case=ChatFeatureTests();case.setUp()
            try:
                case.target.fault=fault
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):case.observe()
                self.assertFalse(case.target.widgets.input_requests)
            finally:case.doCleanups()
        self.target.touch_held=True
        with self.assertRaises(NativeUIError):self.observe()
        self.assertFalse(self.target.widgets.input_requests)
    def test_fresh_reader_cannot_launder_a_replayed_native_view_or_changed_candidate(self):
        self.observe();self.target.fault='view-counter'
        with self.assertRaises(NativeUIError):self.observe()
        self.target.fault='';self.target.binding['processIdentity']='99:replaced'
        with self.assertRaises(NativeUIError):self.observe()
        self.assertIsNotNone(self.flow().store.read())
    def test_consumed_mixer_controller_ack_without_native_node_absence_is_red(self):
        self.observe();self.target.fault='mixer-ack-only'
        with self.assertRaises(NativeUIError):self.act('network-remove-mixer')
        self.assertTrue(self.target.online);self.assertIsNotNone(self.flow().store.read())
    def test_cleanup_restores_setting_once_after_lost_post_restore_journal_return(self):
        self.seed_domain_message();self.act('send');self.activate('cleanup');flow=self.flow();original=flow.owner_save;lost=[False]
        def save():
            original()
            if flow.state['final'] is not None and flow.state['final']['stage']=='peer' and not lost[0]:lost[0]=True;raise OSError('Lost durable cleanup response')
        flow.owner_save=save
        with self.assertRaises(NativeUIError):flow.cleanup(dict(contractVersion=VERSION,runId=self.run))
        handback=self.target.history_source['handbackEpochMs'];self.assertEqual('unset',self.target.history_kind)
        count=sum(row['controlId']=='chat.erase' for row in self.target.widgets.input_requests)
        self.flow().cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertEqual(handback,self.target.history_source['handbackEpochMs']);self.assertEqual(count,sum(row['controlId']=='chat.erase' for row in self.target.widgets.input_requests))
    def test_cleanup_refuses_false_history_handback_and_keeps_original_authority(self):
        self.observe();self.target.fault='history-restore-ack'
        with self.assertRaises(NativeUIError):self.cleanup_now()
        self.assertIsNotNone(self.flow().store.read());self.assertIsNotNone(self.flow().file('peer-capture').read())
        self.target.fault='';self.cleanup_now();self.assertEqual('unset',self.target.history_kind)
    def test_unknown_original_png_change_prevents_retirement(self):
        self.observe();self.act('open');self.observe();self.retire_now()
        path=next(self.root.glob('chat-'+self.run+'-primary-*.png'));path.write_bytes(b'foreign replacement')
        with self.assertRaises(NativeUIError):self.flow().finalize()
        self.assertIsNotNone(self.flow().store.read())
    def test_open_native_actor_result_fd_blocks_finalize_and_actual_release_resumes(self):
        self.observe();self.retire_now();self.target.actor.release=False
        with self.assertRaises(NativeUIError):self.flow().finalize()
        self.assertIsNotNone(self.flow().retirement_store.read());self.assertIsNotNone(self.flow().file('peer-files').read())
        self.target.actor.release=True;self.assertTrue(self.flow().finalize());self.assertTrue(self.flow().finalize())
        self.assertEqual(-1,self.target.actor.fd)
    def test_late_held_touch_blocks_finalization_and_preserves_immutable_authority(self):
        self.observe();self.retire_now();self.target.touch_held=True
        with self.assertRaises(NativeUIError):self.flow().finalize()
        self.assertIsNotNone(self.flow().store.read());self.assertTrue((self.target.actor_root/RESULT).exists())
        self.target.touch_held=False;self.assertTrue(self.flow().finalize());self.assertTrue(self.flow().finalize())

    def test_uncertain_actor_post_is_resolved_from_actual_own_journal_without_republication(self):
        self.observe();flow=self.flow('actor');original=self.actor_client.request;lost=[False];posts=[0]
        def request(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path.endswith('/samples'):
                posts[0]+=1
                if not lost[0]:lost[0]=True;raise OSError('Lost actor transport reply')
            return value
        self.actor_client.request=request
        with self.assertRaises(NativeUIError):flow.publish()
        self.assertIsNotNone(unpack(flow.role_store.read()['payload'])[0]['pending']);before=len(self.client.observe()['entries'])
        self.flow('actor').publish()
        self.assertEqual(before+1,len(self.client.observe()['entries']));self.assertEqual(2,posts[0])
        state=unpack(flow.role_store.read()['payload'])[0];self.assertIsNone(state['pending'])
    def test_adapter_reader_cannot_be_an_actor_or_mutate_the_actor_journal(self):
        with self.assertRaises(NativeUIError):PhoneChatFeature(self.target,'controlled',PhaseFixtureReader(self.primary_client,self.run,'chat'),self.target.config,role='actor')
        with self.assertRaises(NativeUIError):self.primary_client.request('/runs/'+self.run+'/samples',{})

    def registered(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        setup=AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);return setup.f
    def environment(self):
        path=self.root/'chat-configuration.json';access=self.root/'adapter-access.json'
        for file,value in ((path,self.target.config),(access,dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.url,adapterToken='d'*64))):
            store=PrivateFeatureState(file);old=store.read()
            if old is None:store.write(value,None)
            elif old!=value:store.write(value,old)
        return dict(OVERTE_PHONE_FEATURE_CHAT='1',OVERTE_PHONE_CHAT_CONFIGURATION=str(path),OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_E2E_FEATURE_FIXTURE_URL=self.url,
                    OVERTE_PHONE_ACCOUNT_FIXTURE='0')
    def test_registration_is_default_off_closed_and_requires_independent_fixture_inputs(self):
        registered=self.registered();environment=self.environment()
        with patch.dict(os.environ,environment|dict(OVERTE_PHONE_FEATURE_CHAT='0')),patch.object(registered.adapter,'_chat_feature') as factory:
            self.assertFalse(any(op.startswith('feature.chat.') for op in registered.adapter.advertised_capabilities(registered.target)))
            with self.assertRaises(ValueError):registered.adapter.invoke('test-only-appium','feature.chat.observe',dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
            factory.assert_not_called()
        for change in (dict(OVERTE_PHONE_FEATURE_CHAT='yes'),dict(OVERTE_PHONE_CHAT_CONFIGURATION=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL=self.url+'/foreign')):
            with self.subTest(fields=list(change)),patch.dict(os.environ,environment|change),self.assertRaises((RuntimeError,ValueError)):
                registered.adapter.advertised_capabilities(registered.target)
        with patch.dict(os.environ,environment):
            self.assertTrue({'feature.chat.'+kind for kind in ('act','observe','cleanup')}<=set(registered.adapter.advertised_capabilities(registered.target)))
    def test_observer_v6_grammar_keeps_actor_token_separate_and_old_versions_cannot_claim_chat(self):
        from script_observer import configuration
        path=self.root/'chat-observer.json';store=PrivateFeatureState(path)
        value=dict(featureObserverVersion=6,area='chat',target='controlled',candidateArguments=[],fixtureUrl=self.url,actorToken='a'*64,durationSeconds=60)
        store.write(value,None);self.assertEqual(value,configuration(path))
        for change in (dict(featureObserverVersion=3),dict(featureObserverVersion=4),dict(featureObserverVersion=5),dict(expectedMessages=[]),dict(peerTarget='unrelated')):
            store.write(value|change,store.read())
            with self.subTest(change=change),self.assertRaises(NativeUIError):configuration(path)
    def test_full_public_facade_common_25_actions_and_v18_finalization(self):
        from test_chat_foundation import execute_foundation
        execute_foundation(self)
        registered=self.registered();adapter=registered.adapter
        _ui,_observe,binding,_guard,_installed=adapter.normal_feature_runtime('test-only-appium',read_only=True)
        self.target.binding=deepcopy(binding);self.target.config['peer']['actorArtifact']['sourceRevision']=binding['sourceRevision']
        original_class=PhoneChatFeature;original_phase=PhaseFixtureReader
        def flow(_adapter,selector,source,configuration,*,role='primary'):
            return original_class(self.target,selector,source,configuration,role=role,**self.target.options())
        def phase(*args,**kwargs):return original_phase(*args,epoch_ms=self.clock.epoch,monotonic=self.clock.now,**kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,self.environment()))
            stack.enter_context(patch.object(adapter,'state_path',return_value=self.target.state_path('controlled')))
            stack.enter_context(patch('overte_phone_chat_feature.PhoneChatFeature',side_effect=flow))
            stack.enter_context(patch('feature_journeys.phase_fixture.PhaseFixtureReader',side_effect=phase))
            stack.enter_context(patch('overte_session.operation',side_effect=lambda operation,fields:adapter.invoke('test-only-appium',operation,fields)))
            self.assertIsInstance(adapter._chat_feature('test-only-appium',self.run),original_class)
            session=object.__new__(OverteSession)
            self.target.actor_flow=lambda:adapter._chat_feature('test-only-appium',self.run,role='actor',client=self.actor_client)
            def witness():self.target.actor_flow().publish();return self.client.observe()
            Journey('chat',self.run,self.fixture_url,invoke=lambda operation,fields:session.feature_operation('chat',operation.rsplit('.',1)[1],fields),
                witness=witness,activate=self.client.activate,read_artifact=lambda name:(self.root/name).read_bytes(),image_policy={},continuity=lambda *_:None,
                monotonic=self.clock.now,epoch_ms=self.clock.epoch,sleep=self.target.sleep,report=self.reports.append).execute()
            self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertEqual(27,len(self.reports[-1]['phases']))
            self.client.close();self.target.actor_flow().retire_actor()
            fields=dict(contractVersion=VERSION,runId=self.run)
            self.assertEqual({'performed':True},session.feature_operation('chat','cleanup',fields))
            self.assertEqual({'performed':True},session.feature_operation('chat','cleanup',fields))
        self.assertIsNone(self.flow().store.read());self.assertEqual(-1,self.target.actor.fd)

    def test_baseline_reads_original_empty_models_and_two_distinct_receive_sources(self):
        value=self.observe();self.assertEqual([],value['state']['peerMessages']);self.assertFalse(value['state']['open']);self.assertEqual('unset',self.target.history_kind)
        self.assertNotEqual(self.target.primary.value['instance'],self.target.secondary.value['instance']);self.assertTrue(self.target.peer_control.source['leasePresent'])
    def test_all_25_common_actions_and_cleanup_use_original_ordinary_inputs_and_independent_peer(self):
        self.journey().execute();self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertEqual(27,len(self.reports[-1]['phases']))
        self.assertEqual('unset',self.target.history_kind);self.assertFalse(self.target.widgets.ui.panel);self.assertFalse(self.target.widgets.ui.tablet)
        self.client.close();self.flow('actor').retire_actor();self.assertTrue(self.flow().finalize());self.assertTrue(self.flow().finalize())
        self.assertIsNone(self.flow().store.read());self.assertFalse((self.target.actor_root/RESULT).exists());self.assertEqual(-1,self.target.actor.fd)

if __name__=='__main__':unittest.main()
