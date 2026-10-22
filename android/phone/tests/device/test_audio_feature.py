"""Complete public Audio v17 composition over explicit synthetic producers.

The phase service and HTTP input bytes are real loopback sources. Microphone,
codec/peer PCM, Qt widgets and OS processes are synthetic target boundaries;
passing these tests is never native/device or physical audio acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
import wave
from unittest.mock import patch
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.recorded_preview_evidence import RecordedPreviewEvidence,INPUT,SINK
from adapters.token_audio_ui import TokenAudioUI
from feature_journeys.audio_resources import AudioResources
from feature_journeys.engine import Journey
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from overte_phone_audio_feature import PhoneAudioFeature
from overte_phone_audio_fixture import AudioFixtureReader
from overte_phone_audio_peer import PhoneAudioPeer
from overte_phone_audio_source import PhoneAudioSource
from overte_phone_audio_files import wav
from overte_phone_script_history import pack,unpack
from overte_phone_script_lock import PhoneScriptSourceBusy
from self_tests.test_native_feature_observation import Boundary as NativeBoundary


class Clock:
    def __init__(self):self.value=0.;self.base=int(time.time()*1000);self.callback=lambda:None
    def now(self):return self.value
    def epoch(self):return self.base+round(self.value*1000)
    def tick(self):self.value+=.001;return self.epoch()
    def sleep(self,seconds):self.value+=seconds;self.callback()


class Target:
    def __init__(self,path,clock):
        self.path,self.clock=Path(path),clock;self.pid=123;self.birth()
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:456',sessionId='session',generation=1,targetFingerprint='c'*64)
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1);self.foreground=self.running=True
        self.page=False;self.muted=self.echo=False;self.position=.6;self.inputs=[];self.stops=0;self.launches=0;self.fail=None
        self.events=[];self.cycle=0;self.global_event=0;self.started=0;self.captured=self.played=0;self.recording=False
        self.input_pcm=b'';self.sink_pcm=b'';self.stream=[];self.last_update=clock.now();self.exported={};self.input_source=None
        self.domain=str(uuid.uuid4());self.peer=None

    def birth(self):
        self.instance=secrets.token_hex(16);self.ui_instance=secrets.token_hex(16);self.ui_generation=secrets.token_hex(16)
        self.http_instance=secrets.token_hex(16);self.native_seq=self.ui_seq=self.input_seq=self.preview_seq=0;self.elapsed=self.command_sequence=0
    def state_path(self,_):return self.path/'session.json'
    def existing_input_session(self,_):return nullcontext()
    def existing_session(self,_):return self,'session',dict(generation=1)
    def target(self,_):return {}
    def query_app_state(self,*_):return 4 if self.foreground else 2 if self.running else 1
    def process_state(self,*_):return dict(running=self.running,identity=self.binding['processIdentity'] if self.running else None)
    def normal_feature_runtime(self,_,**kwargs):return None,None,deepcopy(self.binding),lambda:self.foreground and self.running,None
    def _graphics_lifecycle_status(self,_,binding):return dict(foreground=self.foreground,binding=deepcopy(binding),running=self.running,appState=self.query_app_state())
    def _audio_voice_status(self,_):return dict(sourceEnabled=False,connected=True,domainId=self.domain,position=dict(x=0.,y=0.,z=0.))

    def event(self,phase,error=''):
        self.global_event+=1;total=144000 if phase!='error' else 0
        self.events.append(dict(schemaVersion=1,eventSequence=self.global_event,publishedEpochMs=self.clock.tick(),phase=phase,error=error,capturedBytes=self.captured,playedBytes=self.played,totalBytes=total))
        self.recording=phase in ('capturing','playing','draining')
    def update(self):
        now=self.clock.now();previous=self.last_update;self.last_update=now
        if self.recording and self.events[-1]['phase']=='capturing' and self.input_source is not None:
            first=max(previous,self.started/1000-self.clock.base/1000);frames=max(0,round((now-first)*24000))
            if frames:
                offset=min(72000,round((first-(self.started-self.clock.base)/1000)*24000));body=self.input_source['raw'][offset*2:min(144000,(offset+frames)*2)]
                self.stream.append((first,body if not self.muted else bytes(len(body))))
        if not self.recording:return
        elapsed=(self.clock.epoch()-self.started)/1000;phase=self.events[-1]['phase']
        captured=min(144000,max(self.captured,round(elapsed*24000)*2));played=min(144000,max(0,round((elapsed-3)*24000)*2))
        if phase=='capturing' and elapsed>=3:
            self.captured=144000;self.played=max(2,played);self.input_pcm=self.input_source['raw'];self.event('playing');phase='playing'
        elif phase=='capturing':
            self.captured=captured
            if self.clock.epoch()-self.events[-1]['publishedEpochMs']>=250:self.event('capturing')
        if phase=='playing':
            self.played=played
            if elapsed>=6:self.played=144000;self.event('draining');phase='draining'
            elif self.clock.epoch()-self.events[-1]['publishedEpochMs']>=250:self.event('playing')
        if phase=='draining' and elapsed>=6.25:
            self.sink_pcm=bytes(144000)+self.input_pcm;self.event('completed')
    def voice(self):
        self.update();events=deepcopy(self.events);active=self.recording
        return dict(active=active,capturedBytes=self.captured if active else 0,playedBytes=self.played if active else 0,frameBytes=2,sampleRate=24000,channels=1,
            event=deepcopy(events[-1]) if events else {},historyVersion=1,cycle=self.cycle,startedEpochMs=self.started,captureSampleRate=24000 if self.cycle else 0,captureChannels=1 if self.cycle else 0,historyComplete=True,events=events)
    def native_send(self,call):
        self.update();self.native_seq+=1;sample=NativeBoundary();sample.send(call);packet=sample.sample
        packet.update(requestId=call['commandId'],instance=self.instance,sequence=self.native_seq,capturedEpochMs=self.clock.tick(),requestedEpochMs=self.clock.epoch(),processId=self.pid,lifecycle=deepcopy(self.lifecycle),animationFence={})
        packet['animation']={};packet['audio']=dict(recording=False,muted=self.muted,recordedVoice=self.voice());self.native_raw=json.dumps(packet)
    def _native_feature_observer(self,_,**kwargs):
        return NativeFeatureObservation(self.native_send,lambda:self.native_raw,self.clock.epoch,lambda:self.foreground,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
    def ui_capture(self):
        self.update();self.ui_seq+=1;self.elapsed+=1
        def row(identifier,ready=True,**fields):return dict(id=identifier,token=hashlib.sha256(repr((identifier,self.cycle,self.muted,self.recording,self.page,self.position)).encode()).hexdigest()[:32],enabled=True,focused=False,inputReady=ready,**fields)
        if not self.page:rows=[row('audio.entry')]
        else:
            phase=self.events[-1]['phase'] if self.events else 'idle'
            rows=[row('audio.page',False,mode=0,nativeHmd=False,uiHmd=False,cycle=self.cycle),row('audio.mode.desktop',checked=True,nativeHmd=False),row('audio.mode.vr',False,checked=False,nativeHmd=False),row('audio.back'),row('audio.mute',checked=self.muted,nativeMuted=self.muted,mode=0),row('audio.record',cycle=self.cycle,nativeActive=self.recording,uiActive=self.recording,requested=False,phase=phase,label='Cancel' if self.recording else 'Start'),row('audio.live-echo',not self.recording,cycle=self.cycle,nativeActive=self.recording,uiActive=self.recording,requested=False,checked=self.echo,nativeEcho=self.echo)]
        return dict(schemaVersion=1,commandId=secrets.token_hex(16),action='observe',instance=self.ui_instance,generation=self.ui_generation,sourceSequence=self.ui_seq,lastCommandSequence=self.command_sequence,elapsedMs=self.elapsed,capturedEpochMs=self.clock.tick(),processId=self.pid,audioControlsVersion=1,ready=True,controls=rows)
    def activate(self,identifier,**kwargs):
        self.update();self.inputs.append(identifier);self.command_sequence+=1
        if self.fail=='ignored-input':return
        if identifier=='audio.entry':self.page=True
        elif identifier=='audio.back':self.page=False
        elif identifier=='audio.mute':
            self.muted=not self.muted
            if self.muted and self.recording:self.event('cancelled','microphone-muted')
        elif identifier=='audio.live-echo':self.echo=not self.echo
        elif identifier=='audio.record':
            if self.recording:self.event('cancelled')
            else:
                self.cycle+=1;self.started=self.clock.tick();self.captured=self.played=0;self.events=[];self.input_pcm=self.sink_pcm=b''
                self.event('error','microphone-muted') if self.muted else self.event('capturing')
        else:raise AssertionError(identifier)
    def _audio_controls(self,_,intent,**kwargs):
        target=self
        class IO:
            def capture(self):return target.ui_capture()
            def activate(self,identifier,**fields):target.activate(identifier,**fields)
        return TokenAudioUI(IO(),intent,monotonic=self.clock.now,sleep=self.clock.sleep)
    def input_send(self,call):
        self.update();self.input_seq+=1;request=call['request'];operation=request['operation']
        if operation=='arm':
            with urlopen(request['url'],timeout=2) as response:raw=response.read();response_id=response.headers['X-Overte-Fixture-Response'];status=response.status
            receipt=dict(runId=request['runId'],ticket=request['ticket'],url=request['url'],responseId=response_id,status=status,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),startedEpochMs=self.clock.tick(),completedEpochMs=self.clock.tick())
            self.input_source=dict(raw=raw,receipt=receipt)
            self.last_fixture=deepcopy(self.input_source)
        elif operation=='release':self.input_source=None
        source=self.input_source
        packet=dict(inputVersion=1,armed=source is not None,receipt=source['receipt'] if source else {},pcmBytes=len(source['raw']) if source else 0,pcmSha256=hashlib.sha256(source['raw'] if source else b'').hexdigest(),complete=True,
            cycle=self.cycle if self.events and self.events[-1]['phase']!='error' else 0,callbacks=len(self.stream),inputFrames=self.captured//2,inputRate=24000,inputChannels=1,firstInputEpochMs=self.started if self.captured else 0,lastInputEpochMs=self.clock.epoch() if self.captured else 0,
            packetEmits=len(self.stream)+1,silentEmits=0,encodedBytes=100,codec='synthetic-opus',inputAvailable=True,lifecycleRunning=True,paused=False,muted=self.muted,preview=self.voice())
        self.input_raw=json.dumps(dict(schemaVersion=1,requestId=call['commandId'],instance=self.http_instance,sequence=self.input_seq,capturedEpochMs=self.clock.tick(),processId=self.pid,pending=False,error='',receipt=source['receipt'] if source else {},source=packet,pendingBytes=0,revision=self.cycle*2))
    def _audio_source(self,_,**kwargs):
        native=SimpleNamespace(pid=self.pid,guard=lambda:self.foreground,clock_ms=self.clock.epoch,send=self.input_send)
        return PhoneAudioSource(native,lambda:self.input_raw,read_only=kwargs.get('read_only',False),monotonic=self.clock.now,sleep=self.clock.sleep)
    def preview_send(self,call):
        self.preview_seq+=1;action=call['action'];request=call['commandId']
        if action=='feature-recorded-audio-release':self.exported={};value=dict(schemaVersion=1,requestId=request,released=True)
        elif action=='feature-recorded-audio-files':value=dict(schemaVersion=1,requestId=request,instance=self.instance,sequence=self.preview_seq,requestedEpochMs=self.clock.tick(),capturedEpochMs=self.clock.tick(),processId=self.pid,files=[dict(name=name,exists=name in self.exported) for name in (INPUT,SINK)],memoryEmpty=not self.exported)
        else:
            self.update();self.exported={INPUT:self.input_pcm,SINK:self.sink_pcm}
            def item(name,tap):
                raw=self.exported[name];return dict(name=name,tap=tap,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            source=dict(cycle=self.cycle,startedEpochMs=self.started,sampleRate=24000,channels=1,inputLastEpochMs=self.started+3000,sinkLastEpochMs=self.clock.epoch(),events=deepcopy(self.events),input=item(INPUT,'capture-before-normalization'),sink=item(SINK,'loopback-device-accepted-write'))
            value=dict(schemaVersion=1,requestId=request,instance=self.instance,sequence=self.preview_seq,requestedEpochMs=self.clock.tick(),capturedEpochMs=self.clock.tick(),processId=self.pid,source=source)
        self.preview_raw=json.dumps(value)
    def _recorded_preview_evidence(self,_,**kwargs):return RecordedPreviewEvidence(self.preview_send,lambda:self.preview_raw,lambda name:self.exported.get(name),self.clock.epoch,lambda:self.foreground,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
    def _process_presence(self,_,**kwargs):
        target=self
        class Presence:
            def require_absent(self,pid):
                if target.fail=='old-alive':raise NativeUIError('Old process still exists')
                return dict(processPresenceVersion=1,commandId=secrets.token_hex(16),instance=target.instance,sequence=target.native_seq+1,requestedEpochMs=target.clock.tick(),capturedEpochMs=target.clock.tick(),processId=target.pid,queryProcessId=pid,presence='absent',nativeResult=-1,nativeError=3,errorSymbol='ESRCH')
        return Presence()
    def invoke(self,_,operation,fields):
        self.update()
        if operation=='lifecycle.background':
            self.foreground=False;self.lifecycle['backgrounds']+=1
            if self.recording:self.event('cancelled','backgrounded')
        elif operation=='app.stop':
            self.stops+=1
            if self.fail!='ignored-stop':self.running=self.foreground=False
        elif operation=='app.launch':
            self.launches+=1;self.foreground=True
            if not self.running:
                self.running=True;self.pid+=1;self.binding['processIdentity']=str(self.pid)+':789';self.birth();self.events=[];self.cycle=0;self.started=0;self.captured=self.played=0;self.recording=False;self.input_source=None
                self.lifecycle['launches']+=1
            self.lifecycle['activations']+=1
        else:raise AssertionError(operation)
        return {'performed':True}


class PeerProducer:
    def __init__(self,target,root,clock):
        self.target,self.root,self.clock=target,Path(root),clock;self.instance=secrets.token_hex(16);self.current=None;self.rows={};self.retired=set();self.position=dict(x=.5,y=0.,z=0.)
        PrivateFeatureState(self.root/'session.json').write(dict(url='http://127.0.0.1:1',token='d'*64),None)
    def update(self):
        if self.current is None:return
        row=self.current
        if self.clock.now()-row['start']<row['seconds']:return
        self.target.update();pcm=bytearray(round(row['seconds']*24000)*2)
        for start,raw in self.target.stream:
            offset=round((start-row['start'])*24000)*2
            begin=max(0,-offset);end=min(len(raw),len(pcm)-offset)
            if begin<end:pcm[offset+begin:offset+end]=raw[begin:end]
        raw=wav(bytes(pcm),24000,1);path=self.root/('preview-'+row['ticket']+'.wav');path.write_bytes(raw);path.chmod(0o600);info=path.stat()
        source=dict(schemaVersion=1,instance=self.instance,captureId=row['ticket'],challenge=row['challenge'],source='private-pc-playout-monitor',startedEpochMs=row['epoch'],completedEpochMs=self.clock.epoch(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),device=info.st_dev,inode=info.st_ino,sampleRate=24000,channels=1,frames=len(pcm)//2,clientSha256='f'*64,runnerSha256='e'*64,pcAudioStats=[dict(capturedEpochMs=self.clock.epoch(),peerSequence=1,audioStats={})],physicalAudioHardwareTested=False)
        self.rows[row['ticket']]=source;self.current=None
    def call(self,root,action,**fields):
        self.update();self.clock.tick()
        if action=='status':return dict(schemaVersion=1,previewProviderVersion=1,recordedPreviewEnabled=True,previewRunnerSha256='e'*64,clientRunning=True,snapshotFresh=True,audioRouted=True,clientSha256='f'*64,snapshotAgeSeconds=.001,receivingPreview=self.current['ticket'] if self.current else None,client=dict(connected=True,mixerReady=True,localEcho=False,serverEcho=False,position=self.position))
        if action=='domain-check':return dict(sameDomain=fields['domain_id']==self.target.domain)
        if action=='position':self.position=dict(x=fields['x'],y=fields['y'],z=fields['z']);return {}
        ticket=fields['capture_id']
        if action=='receive-preview':
            assert self.current is None and ticket not in self.rows and ticket not in self.retired
            self.current=dict(ticket=ticket,challenge=fields['challenge'],seconds=fields['seconds'],start=self.clock.now(),epoch=self.clock.epoch());return dict(retained=True)
        if action=='preview-release':
            path=self.root/('preview-'+ticket+'.wav')
            if path.exists():path.unlink()
            self.rows.pop(ticket,None);self.retired.add(ticket)
            return dict(schemaVersion=1,requestId=fields['request_id'],instance=self.instance,captureId=ticket,capturedEpochMs=self.clock.epoch(),exists=False,retired=True,original=None)
        if action=='preview-files':
            return dict(schemaVersion=1,requestId=fields['request_id'],instance=self.instance,captureId=ticket,capturedEpochMs=self.clock.epoch(),exists=ticket in self.rows,retired=ticket in self.retired,original=deepcopy(self.rows.get(ticket)))
        raise AssertionError(action)


class Executor:
    def __init__(self,peer):self.peer=peer
    def submit(self,callback,*args):
        value=callback(*args);peer=self.peer;ticket=args[1]
        class Future:
            def done(self):peer.update();return ticket in peer.rows or ticket in peer.retired
            def result(self):assert self.done();return value
        return Future()
    def shutdown(self,**kwargs):pass


class AudioFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.state=self.root/'state';self.state.mkdir(mode=0o700);self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700);self.pc=self.root/'pc';self.pc.mkdir(mode=0o700)
        self.clock=Clock();reader,actor,adapter=secrets.token_hex(32),secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(reader,actor,adapter_token=adapter);self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.server.audio_resources=AudioResources(self.url,clock_ms=self.clock.epoch);self.server.journal.clock=self.clock.epoch
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.client=Client(self.url,reader);self.run,self.fixture=self.client.register('audio');self.client.activate('1'*32)
        self.target=Target(self.state,self.clock);self.peer=PeerProducer(self.target,self.pc,self.clock)
        self.config=dict(audioConfigurationVersion=1,artifactRoot=str(self.artifacts),peerState=str(self.pc),peerClientSha256='f'*64,peerRunnerSha256='e'*64,domainId=self.target.domain)
        self.primary=PhoneAudioFeature(self.target,'target',AudioFixtureReader(Client(self.url,adapter),self.run,epoch_ms=self.clock.epoch,monotonic=self.clock.now),self.config,monotonic=self.clock.now,sleep=self.clock.sleep)
        self.actor=PhoneAudioFeature(self.target,'target',AudioFixtureReader(Client(self.url,actor),self.run,epoch_ms=self.clock.epoch,monotonic=self.clock.now),self.config,role='actor',monotonic=self.clock.now,sleep=self.clock.sleep)
        self.patch_peer=patch('overte_phone_audio_feature.PhoneAudioPeer',lambda config,session,guard:PhoneAudioPeer(config,session,guard,call=self.peer.call,epoch_ms=self.clock.epoch));self.patch_peer.start();self.addCleanup(self.patch_peer.stop)
        self.patch_executor=patch('overte_phone_audio_feature.ThreadPoolExecutor',lambda **kwargs:Executor(self.peer));self.patch_executor.start();self.addCleanup(self.patch_executor.stop)
        self.clock.callback=self.publish
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(2);self.assertEqual(0,self.server.internal_errors)
    def publish(self):
        self.target.update();self.peer.update()
        # A real separate actor waits outside the primary's flock. The virtual
        # scheduler cannot block its own input thread for that same OS lock.
        if self.primary.lock._owner is not None or self.actor.lock._owner is not None:return
        try:self.actor.publish()
        except (PhasePending,PhaseRetired,PhoneScriptSourceBusy):pass
    def invoke(self,operation,values):return getattr(self.primary,operation.rsplit('.',1)[1])(values)
    def journey(self):
        self.reports=[]
        return Journey('audio',self.run,self.fixture,invoke=self.invoke,witness=self.client.observe,activate=self.client.activate,
            read_artifact=lambda name:(self.artifacts/name).read_bytes(),image_policy={},continuity=lambda *_:None,
            monotonic=self.clock.now,epoch_ms=self.clock.epoch,sleep=self.clock.sleep,report=self.reports.append)
    def test_complete_common_v17_audio_and_original_two_role_retirement(self):
        self.journey().execute();self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertFalse(self.reports[-1]['deviceAcceptance'])
        self.assertEqual(1,self.target.stops);self.assertEqual(2,self.target.launches)
        self.client.close()
        try:self.actor.publish()
        except PhaseRetired:pass
        # A real source file is checked even when every native/peer flag and
        # retirement counter is otherwise coherent. Preserve its actual inode
        # while exercising missing, modified and incomplete ownership cases.
        with self.primary.lock.held():
            role=self.primary.role_state();record=next(row for row in role['files'] if row['kind']=='input')
        path=self.artifacts/record['name'];backup=path.with_suffix('.held');raw=path.read_bytes()
        path.rename(backup)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        backup.rename(path);path.write_bytes(raw[:-2]+b'xx')
        with self.assertRaises(NativeUIError):self.primary.finalize()
        path.write_bytes(raw)
        store=self.primary.role_store;original=store.read();broken=deepcopy(original);role=unpack(broken['payload'])[0]
        role['files'][0]['phase']='planned';role['files'][0]['file']=None;broken['payload']=pack([role]);store.write(broken,original)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        store.write(original,broken)
        broken=deepcopy(original);role=unpack(broken['payload'])[0];role['quiet']=dict(first=role['quiet']['last'],last=role['quiet']['last'],count=1,complete=False);broken['payload']=pack([role]);store.write(broken,original)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        store.write(original,broken)
        discard=PrivateFeatureState.discard
        def interrupted(store,previous):
            discard(store,previous)
            if store.path.name=='phone-audio-primary.json':raise OSError('Synthetic interruption after a real journal deletion')
        with patch.object(PrivateFeatureState,'discard',interrupted),self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read());self.assertIsNone(self.primary.role_store.read())
        self.target.input_source=deepcopy(self.target.last_fixture)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read());self.target.input_source=None
        self.target.exported={INPUT:b'late-native-pcm'}
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertEqual({INPUT:b'late-native-pcm'},self.target.exported)
        self.assertIsNotNone(self.primary.retirement_store.read());self.target.exported={}
        path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        path.unlink()
        self.primary.finalize();self.primary.finalize()
        self.assertEqual([],list(self.state.glob('phone-audio-*.json')));self.assertEqual([],list(self.artifacts.glob('audio-*.wav')))
        self.assertTrue(self.peer.retired);self.assertEqual({},self.peer.rows)

    def action(self,verb,inputs=None):
        from feature_journeys.scenarios import VERSION
        ticket=secrets.token_hex(16);self.client.activate(ticket,verb,inputs or {})
        self.primary.act(dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture,ticket=ticket,verb=verb,inputs=inputs or {}));return ticket

    def bootstrap(self):self.primary.prepare();self.clock.sleep(.25)

    def test_ignored_normal_open_is_not_replayed_after_a_durable_intent(self):
        self.bootstrap();self.target.fail='ignored-input';ticket=secrets.token_hex(16);self.client.activate(ticket,'open',{})
        from feature_journeys.scenarios import VERSION
        call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture,ticket=ticket,verb='open',inputs={})
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(1,self.target.inputs.count('audio.entry'));self.assertIsNotNone(self.primary.store.read())

    def test_fresh_foreign_process_or_ignored_stop_cannot_restore_idle_history(self):
        from feature_journeys.scenarios import VERSION
        self.bootstrap();self.action('open');ticket=secrets.token_hex(16);self.client.activate(ticket,'cleanup',{})
        self.target.fail='ignored-stop'
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.primary.cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertEqual(1,self.target.stops);self.assertEqual(0,self.target.launches)
        self.assertIsNotNone(self.primary.store.read())

    def test_completed_product_flags_without_actual_codec_emits_stay_red(self):
        self.bootstrap();self.action('open');self.action('record-start');self.action('await-completion');self.clock.sleep(8.5)
        original=self.target.input_send
        def missing_codec(call):
            original(call);value=json.loads(self.target.input_raw);value['source']['silentEmits']=value['source']['packetEmits'];self.target.input_raw=json.dumps(value)
        self.target.input_send=missing_codec
        from feature_journeys.scenarios import VERSION
        with self.assertRaises(NativeUIError):self.primary.observe(dict(contractVersion=VERSION,runId=self.run,afterSequence=0))

    def test_source_binding_does_not_adopt_a_foreign_target_or_same_candidate_new_pid(self):
        self.bootstrap();original=deepcopy(self.target.binding)
        for field,value in (('targetFingerprint','d'*64),('artifactSha256','e'*64),('processIdentity','999:123')):
            with self.subTest(field=field):
                self.target.binding=deepcopy(original);self.target.binding[field]=value
                from feature_journeys.scenarios import VERSION
                with self.assertRaises(NativeUIError):self.primary.observe(dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
        self.target.binding=original


if __name__=='__main__':unittest.main()
