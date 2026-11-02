"""Existing normal recipe and full PC provider with explicit media/OS seams.

Fixture signals are synthetic unit-test inputs, never hardware evidence. No
audio server, client, capture process, device or network service is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_peer import PicoAudioPeer
from adapters.pico4.audio_recipe_evidence import wav
from adapters.recorded_preview_evidence import INPUT,SINK
from adapters.script_journey.history import unpack,pack
from feature_journeys.fixtures import challenge
from self_tests.test_pico_audio_recipe import AudioRecipeFixture
from voice_peer import runtime,voice_signal


class MediaClock:
    def __init__(self,epoch):self.epoch=epoch;self.seconds=0
    def time(self):return (self.epoch+self.seconds*1000)/1000
    def monotonic(self):return self.seconds
    def sleep(self,seconds):self.seconds+=seconds


class AudioRecipeEvidenceTests(AudioRecipeFixture):
    def setUp(self):
        super().setUp()
        self.temp._finalizer.detach();self._cleanups.clear()
        print('Retained Audio recipe/PC originals:',self.path,flush=True)

    def signal_complete(self):
        original=self.native.complete
        def complete():
            original()
            if self.native.cycle==3:
                ticket=self.owner.state['steps'][6]['source']['activations'][-1]['ticket']
                raw=voice_signal.samples(challenge(self.run,ticket).hex(),8000,profile='recorded-preview-v1').tobytes()
                self.native.files={INPUT:raw,SINK:raw}
        self.native.complete=complete
        self.completed()

    def peer(self,*,wrong=False,short=False):
        child=unpack(next(frame['original'] for frame in self.owner.frames
            if frame['action']=='capture3.retain' and frame['stage']=='after')['payload'])[0]
        ticket=child['start']['activations'][-1]['ticket']
        root=self.path/'pc';root.mkdir(mode=0o700,exist_ok=True)
        PrivateFeatureState(root/'session.json').write(dict(url='http://127.0.0.1:1',token='unit-fixture-only'),None)
        worker=runtime.Peer(root,Path('unused'),'hifi://fixture',{})
        worker.client_digest='d'*64
        domain='00000000-0000-0000-0000-000000000001';worker.snapshot=dict(domainId=domain)
        clock=MediaClock(child['original']['source']['startedEpochMs']-100)
        status=lambda:dict(schemaVersion=1,previewProviderVersion=1,recordedPreviewEnabled=True,
            previewRunnerSha256=worker.runner_digest,clientRunning=True,snapshotFresh=True,audioRouted=True,
            clientSha256=worker.client_digest,snapshotAgeSeconds=0,
            client=dict(connected=True,mixerReady=True,localEcho=False,serverEcho=False,sequence=1,audioStats=dict(received=3)))
        sample=challenge(self.run,'0'*32 if wrong else ticket).hex()
        raw=voice_signal.samples(sample,8000,amplitude=.05,profile='recorded-preview-v1').tobytes()
        if short:raw=raw[:8000]
        content=wav(raw,8000,1)
        @contextmanager
        def capture(directory):
            path=directory/'capture.wav';path.write_bytes(content);yield path
        # Execute the complete selected provider method and its physical file
        # ownership checks, while declaring these media/readiness/time seams.
        with patch.dict(runtime.os.environ,OVERTE_E2E_RECORDED_PREVIEW_TESTS='1'),\
             patch.object(worker,'ready',side_effect=lambda **kw:status()),\
             patch.object(worker,'configure',return_value={}),patch.object(worker.routes,'capture',side_effect=capture),\
             patch.object(runtime.time,'time',clock.time),patch.object(runtime.time,'monotonic',clock.monotonic),\
             patch.object(runtime.time,'sleep',clock.sleep),patch.object(runtime.subprocess,'Popen',side_effect=AssertionError('service/process start')):
            worker.run(dict(action='receive-preview',capture_id=ticket,challenge=challenge(self.run,ticket).hex(),seconds=3))
        config=dict(audioConfigurationVersion=1,artifactRoot=str(self.path),peerState=str(root),
                    peerClientSha256=worker.client_digest,peerRunnerSha256=worker.runner_digest,domainId=domain)
        def call(_root,action,**fields):
            if action=='domain-check':fields=dict(domainId=fields['domain_id'])
            with patch.dict(runtime.os.environ,OVERTE_E2E_RECORDED_PREVIEW_TESTS='1'),patch.object(worker,'status',side_effect=status),\
                 patch.object(worker,'ready',side_effect=lambda **kw:status()),patch.object(runtime.time,'time',lambda:self.native.epoch()/1000):
                return worker.run(dict(action=action,**fields))
        peer=PicoAudioPeer(config,None,lambda:True,call=call,epoch_ms=self.native.epoch)
        return peer,worker,ticket,call

    def test_completed_normal_cycle_joins_actual_retained_pcm_and_independent_pc_bytes(self):
        self.signal_complete();peer,worker,ticket,call=self.peer()
        actions=deepcopy(self.native.actions);envelopes=deepcopy(self.native.transport.envelopes)
        result=self.owner.join_completed_preview(peer)
        self.assertEqual(ticket,result['sourceTicket'])
        self.assertNotEqual(self.last_call['ticket'],result['sourceTicket'])
        self.assertTrue(result['independentDigitalMonitorObserved'])
        self.assertFalse(result['physicalAcousticObserved'] or result['independentWholePeerObserved'] or result['fullAudioQualified'])
        self.assertEqual({'input','sink','digitalMonitor'},set(result['analyses']))
        state=deepcopy(self.owner.state['digitalPreview'])
        self.assertEqual('joined',state['phase'])
        cold=self.recipe();again=cold.join_completed_preview(peer)
        self.assertEqual(result,again)
        self.assertEqual(actions,self.native.actions);self.assertEqual(envelopes,self.native.transport.envelopes)
        self.assertEqual(1,len(worker.preview_used));self.assertEqual(set(),worker.preview_retired)
        self.assertTrue((peer.root/('preview-'+ticket+'.wav')).exists())
        # Later normal input still uses the SAME original recipe and sources.
        self.owner=cold;self.act('record-start')
        self.assertEqual(9,self.owner.state['cursor'])

    def test_wrong_actual_pc_signal_keeps_pending_originals_and_blocks_more_input(self):
        self.signal_complete();peer,worker,ticket,call=self.peer(wrong=True)
        actions=deepcopy(self.native.actions)
        with self.assertRaises(NativeUIError):self.owner.join_completed_preview(peer)
        self.assertEqual('issued',self.owner.state['digitalPreview']['phase'])
        self.assertTrue(self.owner.state['digitalPreview']['observations'])
        with self.assertRaises(NativeUIError):self.act('record-start')
        self.assertEqual(actions,self.native.actions)
        with self.assertRaises(NativeUIError):self.recipe().join_completed_preview(peer)
        self.assertEqual(1,len(worker.preview_used));self.assertTrue((peer.root/('preview-'+ticket+'.wav')).exists())

    def test_short_capture_refuses_in_actual_provider_before_parent_join(self):
        self.signal_complete()
        with self.assertRaises(runtime.InfrastructureError):self.peer(short=True)
        self.assertIsNone(self.owner.state['digitalPreview'])

    def test_same_byte_pc_replacement_or_retiming_cannot_reuse_joined_physical_owner(self):
        for fault in ('replacement','retime','metadata-retime'):
            directory=self.path/fault;directory.mkdir(mode=0o700)
            # Each fault uses its own complete original recipe instance.
            # Reuse this class's normal fixture through a separate test object.
            fixture=AudioRecipeEvidenceTests('test_completed_normal_cycle_joins_actual_retained_pcm_and_independent_pc_bytes')
            fixture.setUp()
            try:
                fixture.signal_complete();peer,worker,ticket,_=fixture.peer();fixture.owner.join_completed_preview(peer)
                path=peer.root/('preview-'+ticket+'.wav');raw=path.read_bytes()
                if fault=='replacement':
                    temporary=peer.root/'changed.wav';temporary.write_bytes(raw);temporary.chmod(0o600);temporary.replace(path)
                else:
                    import os
                    if fault=='metadata-retime':path=path.with_suffix('.json')
                    info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1000000))
                with self.assertRaises(NativeUIError):fixture.recipe()
                self.assertTrue(path.exists())
            finally:fixture.doCleanups()

    def test_provider_release_is_owned_and_new_absence_query_does_not_rearm(self):
        self.signal_complete();peer,worker,ticket,call=self.peer()
        with self.assertRaises(ValueError):call(peer.root,'preview-release',capture_id='0'*32,request_id='1'*32)
        worker.receiving_preview=ticket
        with self.assertRaises(runtime.InfrastructureError):peer.release(ticket)
        worker.receiving_preview=None
        absence=peer.release(ticket)
        self.assertTrue(absence['retired']);self.assertFalse(absence['exists'])
        self.assertEqual(1,len(worker.preview_used));self.assertIn(ticket,worker.preview_retired)
        with patch.dict(runtime.os.environ,OVERTE_E2E_RECORDED_PREVIEW_TESTS='1'):
            with self.assertRaises(ValueError):worker.run(dict(action='receive-preview',capture_id=ticket,
                challenge=challenge(self.run,ticket).hex(),seconds=3))

    def test_old_recipe_v1_reads_without_migration_or_new_input(self):
        self.owner.prepare();disk=self.owner.store.read();body=unpack(disk['payload'])[0];body.pop('digitalPreview')
        old=dict(disk,audioRecipeVersion=1,payload=pack([body]));self.owner.store.write(old,disk)
        cold=self.recipe();self.assertEqual(1,cold.version);self.assertEqual(old,cold.store.read())
        self.assertEqual([],self.native.actions)

    def test_real_outer_exit_cannot_publish_aged_digital_join(self):
        self.signal_complete();peer,worker,ticket,_=self.peer()
        actions=deepcopy(self.native.actions);held=self.owner.lock.held
        @contextmanager
        def slow_exit():
            with held():yield
            if self.owner.lock._owner is None:self.native.clock+=2
        with patch.object(self.owner.lock,'held',slow_exit),self.assertRaises(NativeUIError):
            self.owner.join_completed_preview(peer)
        self.assertEqual('joined',self.owner.state['digitalPreview']['phase'])
        self.assertTrue(self.owner.state['digitalPreview']['metadata']['raw'])
        self.assertEqual(actions,self.native.actions)
        self.assertTrue((peer.root/('preview-'+ticket+'.wav')).exists())

    def test_lost_joined_parent_return_recovers_by_original_reads_without_new_receive(self):
        self.signal_complete();peer,worker,ticket,_=self.peer();save=self.owner.save
        def lost(state,**kwargs):
            save(state,**kwargs)
            if state['digitalPreview'] is not None and state['digitalPreview']['phase']=='joined':
                raise NativeUIError('Explicit lost joined parent return')
        actions=deepcopy(self.native.actions)
        with patch.object(self.owner,'save',side_effect=lost),self.assertRaises(NativeUIError):
            self.owner.join_completed_preview(peer)
        self.assertEqual('joined',self.owner.state['digitalPreview']['phase'])
        result=self.recipe().join_completed_preview(peer)
        self.assertTrue(result['independentDigitalMonitorObserved']);self.assertEqual(1,len(worker.preview_used))
        self.assertEqual(actions,self.native.actions)

    def test_original_cli_forwards_closed_preview_request_without_service_activation(self):
        root=Path(__file__).resolve().parents[1]/'voice_peer'
        sys.path.insert(0,str(root))
        try:
            spec=importlib.util.spec_from_file_location('pico_audio_original_cli',root/'voice_peer.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:sys.path.remove(str(root))
        for action in ('receive-preview','preview-files','preview-release'):
            ticket='1'*32;extra=['--challenge','2'*32,'--seconds','3'] if action=='receive-preview' else ['--request-id','3'*32]
            argv=['voice_peer.py','--state-dir',str(self.path),action,'--capture-id',ticket,*extra]
            with patch.object(sys,'argv',argv),patch.object(module,'control',return_value={}) as control,redirect_stdout(io.StringIO()):
                self.assertEqual(0,module.main())
            request=control.call_args.args[1]
            self.assertEqual(action,request['action']);self.assertEqual(ticket,request['capture_id'])
            self.assertEqual({'action','capture_id','challenge','seconds'} if action=='receive-preview'
                             else {'action','capture_id','request_id'},set(request))

    def test_valid_signal_with_false_provider_wav_geometry_is_refused(self):
        self.signal_complete();peer,worker,ticket,_=self.peer()
        path=peer.root/('preview-'+ticket+'.json');value=json.loads(path.read_text())
        value.update(sampleRate=16000,frames=48000);path.write_text(json.dumps(value));path.chmod(0o600)
        actions=deepcopy(self.native.actions)
        with self.assertRaises(NativeUIError):self.owner.join_completed_preview(peer)
        self.assertEqual('issued',self.owner.state['digitalPreview']['phase'])
        self.assertTrue(self.owner.state['digitalPreview']['observations'])
        self.assertEqual(actions,self.native.actions)


if __name__=='__main__':unittest.main()
