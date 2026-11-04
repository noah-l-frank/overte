"""Normal Audio owners plus real owned host workers; audio/OS/route are models.

No audio program, server, device, compiler or physical capture is started.
The stdin-only Python workers provide actual Linux process/birth originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4.audio_pc_source import validate,accept
from adapters.normal_ui import NativeUIError
from voice_peer.preview_source import PreviewSources,PreviewSourceUnavailable,process
from voice_peer import runtime,voice_signal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_pc_actor import PicoAudioPCActor
from adapters.pico4.audio_pc_start import PicoAudioPCStartCoordinator
from adapters.pico4.audio_peer import PicoAudioPeer
from adapters.pico4.audio_recipe import INPUTS
from adapters.recorded_preview_evidence import INPUT,SINK
from feature_journeys.fixtures import challenge
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from adapters.script_journey.history import unpack
from self_tests.test_pico_audio_recipe import AudioRecipeFixture


class AudioPCSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.temp._finalizer.detach();self.root=Path(self.temp.name)
        print('Retained original Audio PC source fixture:',self.root,flush=True)
        self.streams=[];self.client=self.spawn();self.recorder=self.spawn();self.ticket=uuid.uuid4().hex;self.request=uuid.uuid4().hex
        self.sources=PreviewSources(lambda:deepcopy(self.streams),'unit-owned-monitor',17,lambda:int(time.time()*1000),
            self.client,process(self.client.pid)['executable'])
        self.record=self.sources.claim(self.ticket,self.request,8)
    def spawn(self):
        worker=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.addCleanup(self.finish,worker);return worker
    @staticmethod
    def finish(worker):
        if not worker.stdin.closed:worker.stdin.close()
        worker.wait(timeout=5)
    def route(self):
        self.streams=[dict(index=73,source=17,corked=False,properties={'application.process.id':str(self.recorder.pid)})]
    def armed(self):
        self.record.created(self.recorder);self.route();self.record.armed(self.recorder)
    def packet(self):
        request=uuid.uuid4().hex;packet=self.sources.query(self.ticket,request,used=True)
        validate(packet,self.ticket,request,int(time.time()*1000))
        path=self.root/('query-'+request+'.json');path.write_text(json.dumps(packet));path.chmod(0o600);return packet
    def closed(self):
        self.finish(self.recorder);self.streams=[];self.record.closed()

    def test_actual_kernel_birth_and_current_route_are_required_for_capturing(self):
        before=self.packet();self.assertEqual('issued',before['source']['state']);self.assertIsNone(before['source']['worker'])
        self.armed();current=self.packet();accept(before,current)
        self.assertEqual('capturing',current['source']['state']);self.assertEqual(self.request,current['source']['armRequestId'])
        self.assertEqual(str(self.recorder.pid),current['source']['worker']['identity'].split(':')[0])
        self.assertEqual(str(self.client.pid),current['clientProcess']['identity'].split(':')[0])
        self.assertEqual(17,current['source']['route']['sourceIndex'])

    def test_wrong_actual_stream_route_never_becomes_armed(self):
        self.record.created(self.recorder);self.route();self.streams[0]['source']=18
        with self.assertRaises(PreviewSourceUnavailable):self.record.armed(self.recorder)
        self.assertEqual('starting',self.record.state);self.assertIsNone(self.record.route)

    def test_corked_stream_and_actual_stopped_recorder_cannot_be_ready(self):
        self.armed();self.streams[0]['corked']=True
        with self.assertRaises(PreviewSourceUnavailable):self.packet()
        self.streams[0]['corked']=False
        os.kill(self.recorder.pid,signal.SIGSTOP)
        self.addCleanup(lambda:os.kill(self.recorder.pid,signal.SIGCONT) if self.recorder.poll() is None else None)
        # Wait for the actual kernel stop, never infer it from kill's return.
        for _ in range(100):
            status=Path('/proc',str(self.recorder.pid),'stat').read_text().rsplit(')',1)[1].split()[0]
            if status=='T':break
            threading.Event().wait(.001)
        self.assertEqual('T',status)
        with self.assertRaises(PreviewSourceUnavailable):self.packet()

    def test_changed_original_worker_birth_refuses_current_source(self):
        self.armed();self.record.worker['identity']=self.record.worker['identity'].replace(':',':999',1)
        with self.assertRaises(PreviewSourceUnavailable):self.packet()

    def test_alive_recorder_cannot_claim_exit_or_release(self):
        self.armed()
        with self.assertRaises(PreviewSourceUnavailable):self.record.closed()
        self.record.failed()
        with self.assertRaises(PreviewSourceUnavailable):self.record.retired()
        self.assertIsNone(self.record.exit);self.assertIsNone(self.recorder.poll())

    def test_actual_exit_and_stream_absence_survive_new_queries(self):
        self.armed();old=self.packet();self.closed();current=self.packet();accept(old,current)
        self.assertEqual('closed',current['source']['state']);self.assertTrue(current['source']['exit']['processAbsent'])
        self.assertTrue(current['source']['exit']['streamAbsent']);self.assertIsNotNone(self.recorder.poll())

    def test_late_stream_after_real_exit_prevents_quiet_source(self):
        self.armed();self.closed();self.route()
        with self.assertRaises(PreviewSourceUnavailable):self.packet()

    def test_replaced_actual_client_and_replayed_request_refuse(self):
        self.armed();packet=self.packet()
        with self.assertRaises(PreviewSourceUnavailable):self.sources.query(self.ticket,packet['requestId'],used=True)
        self.sources.client=self.spawn()
        with self.assertRaises(PreviewSourceUnavailable):self.packet()

    def test_foreign_received_source_or_stale_sequence_does_not_advance_reader(self):
        self.armed();packet=self.packet()
        with self.assertRaises(NativeUIError):accept(packet,deepcopy(packet))
        changed=deepcopy(packet);changed.update(sequence=packet['sequence']+1,requestId=uuid.uuid4().hex)
        changed['source']['generation']=uuid.uuid4().hex
        with self.assertRaises(NativeUIError):accept(packet,changed)


class ModelPC:
    """Real provider/file code and kernel workers; Pulse/media/time are models."""
    def __init__(self,test):
        self.test=test;self.native=test.f.native;self.root=test.f.path/'pc';self.root.mkdir(mode=0o700)
        self.client=self.spawn();self.recorders=[];self.rows=[];self.requests=[];self.stopping=False;self.wake=threading.Event();self.sequence=0
        self.ignore_receive=False;self.foreign_source=False;self.lose_reply_once=False;self.lost_returns=0
        self.worker=runtime.Peer(self.root,Path(sys.executable),'hifi://unit-controlled',{})
        self.worker.client=self.client;self.worker.client_file=tuple(process(self.client.pid)['executable'])
        self.worker.client_digest=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        self.worker.routes.sources={'rx':17};self.worker.snapshot=dict(domainId='00000000-0000-0000-0000-000000000001')
        self.worker.status=self.status;self.worker.ready=self.ready;self.worker.configure=lambda **_fields:self.status()
        self.worker.routes.capture=self.capture
        PrivateFeatureState(self.root/'session.json').write(dict(url='http://127.0.0.1:1',token='owned-unit-controller-token-only'),None)
        self.config=dict(audioConfigurationVersion=1,artifactRoot=str(test.f.path),peerState=str(self.root),
            peerClientSha256=self.worker.client_digest,peerRunnerSha256=self.worker.runner_digest,domainId=self.worker.snapshot['domainId'])
    def spawn(self):
        return subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    def status(self):
        self.sequence+=1
        return dict(schemaVersion=1,previewProviderVersion=1,recordedPreviewEnabled=True,previewRunnerSha256=self.worker.runner_digest,
            clientRunning=self.client.poll() is None,snapshotFresh=True,audioRouted=True,clientSha256=self.worker.client_digest,snapshotAgeSeconds=0,
            client=dict(connected=True,mixerReady=True,muted=True,localEcho=False,serverEcho=False,sequence=self.sequence,audioStats=dict(received=0)))
    def ready(self,**_kwargs):
        value=self.status()
        if not value['clientRunning']:raise runtime.InfrastructureError('Owned model client exited')
        return value
    def sleep(self,seconds):
        if self.stopping:raise runtime.InfrastructureError('Owned model capture closing')
        self.wake.wait(.002);self.wake.clear()
        if self.stopping:raise runtime.InfrastructureError('Owned model capture closing')
    def advance(self,seconds):
        self.native.sleep(seconds);self.wake.set();threading.Event().wait(.001)
    @contextmanager
    def capture(self,directory,*,source=None):
        recorder=self.spawn();self.recorders.append(recorder);source.created(recorder)
        row=dict(index=len(self.recorders)+100,source=17,corked=False,properties={'application.process.id':str(recorder.pid)})
        self.rows.append(row);source.armed(recorder);started=self.native.epoch();path=directory/'capture.wav'
        try:yield path
        finally:
            AudioPCSourceTests.finish(recorder);self.rows.remove(row);source.closed()
            # Explicit receiver/media model: copy the original completed native
            # sink bytes; other captures contain independent modeled silence.
            raw=self.native.files.get(SINK,b'') if self.native.cycle==3 else b''
            ticket=source.capture;start=self.native.record_starts.get(self.native.cycle,started)
            prefix=b'\0\0'*max(0,round((start-started)*8))
            frames=round(source.seconds*8000);content=(prefix+raw+b'\0\0'*frames)[:frames*2]
            with wave.open(str(path),'wb') as output:output.setparams((1,2,8000,0,'NONE','not compressed'));output.writeframes(content)
    def call(self,_root,action,**fields):
        self.requests.append(dict(action=action,fields=deepcopy(fields)))
        if action=='domain-check':fields=dict(domainId=fields['domain_id'])
        if action=='receive-preview-owned' and self.ignore_receive:return dict(schemaVersion=1,captureId=fields['capture_id'],retained=True)
        result=self.worker.run(dict(action=action,**fields))
        if action=='preview-source' and self.foreign_source and result['source'] is not None and result['source']['state']=='capturing':
            result=deepcopy(result);result['source']['worker']['identity']=result['source']['worker']['identity'].replace(':',':999',1)
        if action=='receive-preview-owned' and self.lose_reply_once:
            self.lose_reply_once=False;self.lost_returns+=1
            raise RuntimeError('Modeled lost reply after actual owned recorder completion')
        return result
    def raw_call(self,root,action,*,_literal,**fields):
        token=_literal.before(action,fields)
        lost=action=='receive-preview-owned' and self.lose_reply_once
        if lost:self.lose_reply_once=False
        try:result=self.call(root,action,**fields)
        except BaseException:
            _literal.uncertain(token,None);raise
        raw=json.dumps(result).encode('utf-8');_literal.after(token,raw)
        if lost:self.lost_returns+=1;raise RuntimeError('Modeled lost return AFTER exact stdout retention')
        from adapters.native_feature_observation import decode
        return decode(raw.decode('utf-8'))
    def peer(self):return PicoAudioPeer(self.config,None,lambda:True,call=self.call,epoch_ms=self.native.epoch,raw_call=self.raw_call)
    def close(self):
        self.stopping=True;self.wake.set()
        if getattr(self.test,'actor',None) is not None:
            for future in self.test.actor.jobs.values():
                try:future.result(timeout=5)
                except Exception:
                    import traceback
                    traceback.print_exc()
            if self.test.actor.executor is not None:self.test.actor.executor.shutdown(wait=True)
        for recorder in self.recorders:AudioPCSourceTests.finish(recorder)
        AudioPCSourceTests.finish(self.client)


class AudioPCStartTests(unittest.TestCase):
    recipe_fixture=AudioRecipeFixture
    def create_cleanup_budget(self):return None
    def setUp(self):
        self.f=getattr(self,'recipe_fixture',AudioRecipeFixture)();self.f.setUp();self.f.temp._finalizer.detach();self.addCleanup(self.f.doCleanups)
        self.f._cleanups=[row for row in self.f._cleanups if getattr(row[0],'__self__',None) is not self.f.temp]
        print('Retained original Audio armed normal recipe:',self.f.path,flush=True)
        self.actor=None;self.pc=ModelPC(self)
        changes=(patch.dict(os.environ,OVERTE_E2E_RECORDED_PREVIEW_TESTS='1',OVERTE_E2E_PICO_AUDIO_SOURCE_TESTS='1'),
            patch.object(runtime,'pulse_list',side_effect=lambda kind:deepcopy(self.pc.rows)),
            patch.object(runtime,'time',SimpleNamespace(time=lambda:self.f.native.epoch()/1000,
                monotonic=lambda:self.f.native.clock,sleep=self.pc.sleep)))
        for change in changes:change.start();self.addCleanup(change.stop)
        self.addCleanup(lambda:self.actor.raws.close_host() if self.actor is not None else None)
        self.addCleanup(self.pc.close)
        parent=self.f.native.owner();native=self.f.native.native.reader();native.guard=self.f.native.guard
        native.clock_ms=self.f.native.epoch;native.monotonic=lambda:self.f.native.clock;native.sleep=self.f.native.sleep
        test=self
        class ActorClient(Client):
            def request(self,path,value=None,*args,phase_nonce=None,**kwargs):
                if phase_nonce is not None:return test.f.journal.phase(test.f.run,phase_nonce)
                if path.endswith('/samples'):test.f.journal.publish(test.f.run,value);return dict(accepted=True)
                test.assertEqual('/runs/'+test.f.run,path);return test.f.journal.snapshot(test.f.run)
        source=PhaseFixtureReader(ActorClient(self.f.source.client.url,'b'*64),self.f.run,'audio',
            monotonic=lambda:self.f.native.clock,epoch_ms=self.f.native.epoch)
        budget_factory=getattr(self,'create_cleanup_budget',None)
        cleanup_budget=None if budget_factory is None else budget_factory()
        self.actor=PicoAudioPCActor(self.f.owner,source,self.pc.peer,native,parent.settings,parent.pages,self.f.status,
            monotonic=lambda:self.f.native.clock,sleep=self.pc.advance,cleanup_budget=cleanup_budget)
        self.owner=PicoAudioPCStartCoordinator(self.f.owner,self.actor)
        complete=self.f.native.complete
        def original_complete():
            complete()
            if self.f.native.cycle==3:
                ticket=self.f.owner.state['steps'][6]['source']['activations'][-1]['ticket']
                raw=voice_signal.samples(challenge(self.f.run,ticket).hex(),8000,profile='recorded-preview-v1').tobytes()
                self.f.native.files={INPUT:raw,SINK:raw}
        self.f.native.complete=original_complete
    def act(self,verb,inputs=None):
        ticket=self.f.activate(verb,inputs);self.last_call=dict(contractVersion=16,runId=self.f.run,fixtureUrl=self.f.source.fixture_url,
            ticket=ticket,verb=verb,inputs={} if inputs is None else inputs)
        return self.owner.act(self.last_call)
    def full(self):
        self.owner.prepare();self.actor.publish()
        for index,(verb,inputs) in enumerate(INPUTS):
            if verb=='await-completion':self.f.native.auto_complete=True
            if verb=='close':
                def callbacks(seconds):
                    self.f.native.sleep(seconds)
                    for cycle,epoch in self.f.native.record_starts.items():
                        if cycle not in self.f.native.callback_events and self.f.native.epoch()-epoch>=30000:
                            self.f.native.callback_events[cycle]=dict(enteredEpochMs=self.f.native.epoch(),completedEpochMs=self.f.native.epoch(),retiredEpochMs=self.f.native.epoch(),retired=True)
                self.f.owner.child('page.prepare').settings.sleep=callbacks
            self.act(verb,inputs);self.f.native.auto_complete=False;self.actor.publish()

    def test_same_fourteen_normal_actions_independent_originals_and_actual_digital_recorder_handback(self):
        self.pc.lose_reply_once=True
        self.full();actions=deepcopy(self.f.native.actions);streams=deepcopy(self.f.native.transport.envelopes)
        result=self.owner.retire_digital()
        self.assertEqual(14,result['normalStagesDispatched']);self.assertTrue(result['digitalRecorderRetired'])
        self.assertFalse(result['fullAudioQualified'] or result['physicalAcousticObserved'])
        self.assertEqual(actions,self.f.native.actions);self.assertEqual(streams,self.f.native.transport.envelopes)
        self.assertEqual(5,len(self.actor.state['jobs']));self.assertTrue(all(row['retired'] for row in self.actor.state['jobs']))
        self.assertTrue(self.actor.state['quiet']['complete']);self.assertTrue(all(worker.poll() is not None for worker in self.pc.recorders))
        self.assertEqual(5,len(list(self.pc.root.glob('preview-*.wav'))));self.assertEqual(5,len(list(self.pc.root.glob('preview-*.json'))))
        self.assertEqual(15,len(self.f.journal.snapshot(self.f.run)['entries']))
        self.assertEqual('joined',self.f.owner.state['digitalPreview']['phase'])
        self.assertEqual(1,self.pc.lost_returns)
        self.assertEqual(5,sum(row['action']=='receive-preview-owned' for row in self.pc.requests))

    def before_record(self):
        self.owner.prepare();self.act('open');self.act('mute',dict(enabled=True))

    def test_ignored_receive_ack_cannot_authorize_actual_normal_record(self):
        self.before_record();self.pc.ignore_receive=True;before=deepcopy(self.f.native.actions)
        with self.assertRaises(NativeUIError):self.act('record-start')
        self.assertEqual(before,self.f.native.actions);self.assertEqual([],self.pc.recorders)
        self.assertEqual('waiting-pc',self.owner.state['phase'])
        with self.assertRaises(NativeUIError):self.owner.act(deepcopy(self.last_call))
        self.assertEqual(1,sum(row['action']=='receive-preview-owned' for row in self.pc.requests))

    def test_foreign_actual_worker_source_retains_reply_and_sends_zero_record(self):
        self.before_record();self.pc.foreign_source=True;before=deepcopy(self.f.native.actions)
        with self.assertRaises(NativeUIError):self.act('record-start')
        self.assertEqual(before,self.f.native.actions);self.assertIsNotNone(self.actor.state['pending'])
        self.assertTrue(any(row.get('label')=='pc-reply' for row in self.actor.state['pending']['raws']))
        count=sum(row['action']=='receive-preview-owned' for row in self.pc.requests)
        with self.assertRaises(NativeUIError):self.owner.act(deepcopy(self.last_call))
        self.assertEqual(count,sum(row['action']=='receive-preview-owned' for row in self.pc.requests))

    def after_record_cas(self,callback):
        write=PrivateFeatureState.write;changed=[]
        def landed(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.f.owner.store.path and not changed and value.get('audioRecipeVersion')==2:
                state=unpack(value['payload'])[0];pending=state['pending']
                if pending is not None and pending['name']=='page.record' and pending['deliveries'] \
                        and pending['deliveries'][-1]['original'].get('controlId')=='audio.record':
                    changed.append(True);callback()
            return answer
        return patch.object(PrivateFeatureState,'write',landed),changed

    def test_real_recorder_death_after_finished_command_cas_sends_zero_normal_record(self):
        self.before_record();before=deepcopy(self.f.native.actions);at_cas=[]
        def die():
            at_cas.extend(self.f.native.actions);AudioPCSourceTests.finish(self.pc.recorders[-1])
        change,changed=self.after_record_cas(die)
        with change,self.assertRaises(NativeUIError):self.act('record-start')
        self.assertTrue(changed);self.assertEqual(at_cas,self.f.native.actions)
        self.assertEqual(before.count('audio.record'),self.f.native.actions.count('audio.record'))
        self.assertEqual('page.record',self.f.owner.state['pending']['name']);self.assertTrue(self.f.owner.state['pending']['deliveries'])

    def test_same_byte_parent_replacement_after_command_cas_preserves_intent_and_sends_zero_record(self):
        self.before_record();before=deepcopy(self.f.native.actions);at_cas=[]
        def replace():
            at_cas.extend(self.f.native.actions)
            path=self.owner.store.path;other=path.with_name('replacement-parent.json');other.write_bytes(path.read_bytes());other.chmod(0o600);os.replace(other,path)
        change,changed=self.after_record_cas(replace)
        with change,self.assertRaises(NativeUIError):self.act('record-start')
        self.assertTrue(changed);self.assertEqual(at_cas,self.f.native.actions)
        self.assertEqual(before.count('audio.record'),self.f.native.actions.count('audio.record'))
        self.assertTrue(self.f.owner.state['pending']['deliveries']);self.assertEqual('acting',self.owner.store.read()['state']['phase'])

    def test_lost_actor_publication_return_resolves_exact_get_without_reposting_old_fact(self):
        self.owner.prepare();baseline=self.actor.state['sequence'];request=self.actor.source.client.request;lost=[]
        def delivered(path,*args,**kwargs):
            result=request(path,*args,**kwargs)
            if path.endswith('/samples') and not lost:lost.append(True);raise RuntimeError('Modeled lost actual POST response')
            return result
        self.actor.source.client.request=delivered
        with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertIsNotNone(self.actor.state['publication']);self.assertEqual(1,len(self.f.journal.snapshot(self.f.run)['entries']))
        packet=self.actor.publish();self.assertEqual(baseline+2,packet['actorSequence'])
        self.assertEqual([baseline+1,baseline+2],[row['actorSequence'] for row in self.f.journal.snapshot(self.f.run)['entries']])
        self.assertIsNone(self.actor.state['publication']);self.assertEqual([],self.f.native.actions)

    def test_native_and_pc_three_second_span_cannot_replace_frozen_independent_host_quiet(self):
        self.full();self.actor.retire_recorders();before=deepcopy(self.f.native.actions)
        current=self.actor.monotonic();self.actor.monotonic=lambda:current
        advances=[];stopped=[]
        def native_only(seconds):
            if len(advances)==12:
                window=self.actor.state['quiet']
                self.assertTrue(all(new-old>=3000 for new,old in zip(window['last'],window['first'])))
                self.assertTrue(all(window['lastPC'][key]-old>=3000 for key,old in window['firstPC'].items()))
                self.assertEqual(0,window['lastHost']-window['firstHost']);self.assertFalse(window['complete'])
                stopped.append(True);raise NativeUIError('Bounded counter ended after actual native-only quiet span')
            advances.append(seconds);self.pc.advance(seconds)
        self.actor.sleep=native_only
        with self.assertRaises(NativeUIError):self.actor.quiet()
        self.assertTrue(stopped);self.assertEqual(before,self.f.native.actions);self.assertFalse(self.owner.state['digitalRetired'])


if __name__=='__main__':unittest.main()
