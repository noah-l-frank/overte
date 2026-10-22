"""Real private journals/static HTTP; native acquisition ports are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner,SOURCES
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.self_tests import test_ios_navigation_scene_admission as admission_tests
from ios.self_tests.test_ios_navigation_state import RUN
from self_tests.test_completed_frame_lease import BINDING


class Native(NativeFeatureObservation):
    def __init__(self,harness):
        self.harness=harness;self.ios=True;self.pid=42;self.sequence=0;self.guard=lambda:harness.okay
    def read(self,after):
        self.harness.reads.append('native');self.sequence+=1
        value=deepcopy(self.harness.fixture.join['nativeBefore' if self.sequence==1 else 'nativeAfter'])
        self.harness.advance(value['capturedEpochMs']);return value


class NavigationAdmissionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=admission_tests.NavigationSceneAdmissionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.okay=True;self.reads=[];self.fault=None
        self.host=time.time()*1000;self.ms=0;self.native_first=self.fixture.join['nativeBefore']['capturedEpochMs']
        self.native=Native(self)
        self.provider=NavigationFixtureReader(self.fixture.harness.client,RUN);self.provider.attach()
        self.sources={}
        for name,kind in SOURCES.items():
            def read(_reader,run=None,name=name):
                self.reads.append(name)
                if self.fault==name:raise OSError('Synthetic lost native source return')
                value=deepcopy(self.fixture.originals[name])
                epoch=value.get('sampleEpochMs',value.get('capturedEpochMs'))
                if epoch is None:epoch=value['clockAfter']['epochMs']
                self.advance(epoch);return value
            reader=type('ModeledOriginal', (kind,), {'__init__':lambda _self:None,'read':read,'capture':read})()
            reader.pid=42;reader.ios=True;self.sources[name]=reader

    def advance(self,epoch):self.ms=max(self.ms,epoch-self.native_first)
    def epoch(self):return self.host+self.ms
    def mono(self):return 10.+self.ms/1000
    def owner(self,*,historical=False,run=RUN,binding=BINDING):
        return NavigationAdmissionOwner(PrivateFeatureState(self.root/'ios-navigation-scene-admission.json'),
            binding,run,self.lock,lambda:self.okay,historical=historical,
            native=None if historical else self.native,sources=None if historical else self.sources,
            fixture=None if historical else self.provider,epoch_ms=self.epoch,monotonic=self.mono)
    def take(self,owner):return owner.acquire(self.epoch()-1)

    def test_eight_originals_are_sealed_and_historical_read_never_calls_native_or_http(self):
        with self.lock.held():
            owner=self.owner();proof=self.take(owner);self.assertEqual('admitted',owner.state['phase'])
            self.assertEqual(set(SOURCES),set(proof['originals']));self.assertEqual(proof,owner.for_input())
            self.assertEqual(['native',*SOURCES,'native'],self.reads)
            retained=deepcopy(owner.store.read());reads=list(self.reads);self.okay=False
            self.provider.client.request=lambda *_:self.fail('Historical validation made HTTP call')
            historical=self.owner(historical=True);self.assertEqual(proof,historical.archive())
            self.assertEqual(reads,self.reads);self.assertEqual(retained,historical.store.read())
            with self.assertRaises(NativeUIError):historical.for_input()

    def test_lost_middle_read_retains_begin_and_prefix_without_a_second_acquisition(self):
        with self.lock.held():
            self.fault='http';owner=self.owner()
            with self.assertRaises(OSError):self.take(owner)
            self.assertEqual({'inventory','navigation','bookmarks','model'},set(owner.state['originals']))
            self.assertIsNotNone(owner.state['nativeStart']);self.assertIsNone(owner.state['nativeEnd'])
            retained=deepcopy(owner.store.read());reads=list(self.reads);self.fault=None;again=self.owner()
            with self.assertRaises(NativeUIError):self.take(again)
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(retained,again.store.read());self.assertEqual(reads,self.reads)

    def test_lost_final_result_only_recovers_original_proof_and_cannot_refresh_input_deadline(self):
        with self.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['phase']=='admitted':raise OSError('Synthetic lost final result write')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):self.take(owner)
            owner.store.write=write;again=self.owner();reads=list(self.reads)
            originals=deepcopy(again.state['originals']);self.ms+=2000
            self.assertIsNone(again.recover());self.assertEqual(originals,again.archive()['originals'])
            self.assertEqual(reads,self.reads)
            with self.assertRaises(NativeUIError):again.for_input()

    def test_late_original_end_is_retained_but_refuses_recovery_without_rereading(self):
        with self.lock.held():
            owner=self.owner();original=self.native.read
            def late(after):
                packet=original(after)
                if self.native.sequence==2:self.ms+=2000
                return packet
            self.native.read=late
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertIsNotNone(owner.state['nativeEnd']);self.assertIsNotNone(owner.state['clockJoin'])
            reads=list(self.reads);again=self.owner()
            with self.assertRaises(NativeUIError):again.recover()
            self.assertEqual(reads,self.reads)

    def test_rejected_pose_stays_owned_and_a_new_run_or_binding_cannot_bypass_it(self):
        with self.lock.held():
            self.fixture.originals['navigation']['source']['view']['mode']='third person';owner=self.owner()
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertEqual(8,len(owner.state['originals']));self.assertEqual('reading',owner.state['phase'])
            with self.assertRaises(NativeUIError):self.owner(run='f'*32,historical=True)
            changed=dict(BINDING,sessionId='foreign-sdk')
            with self.assertRaises(NativeUIError):self.owner(binding=changed,historical=True)
            reads=list(self.reads)
            with self.assertRaises(NativeUIError):self.owner().recover()
            self.assertEqual(reads,self.reads)

    def test_provider_change_or_external_journal_replacement_is_refused_before_more_reads(self):
        with self.lock.held():
            owner=self.owner();self.take(owner);reads=list(self.reads)
            self.provider.instance='f'*32
            with self.assertRaises(NativeUIError):owner.for_input()
            self.provider.instance=owner.state['providerInstance']
            raw=owner.store.read();changed=deepcopy(raw);changed['runId']='f'*32;owner.store.write(changed,raw)
            with self.assertRaises(NativeUIError):owner.for_input()
            self.assertEqual(reads,self.reads)

    def test_static_source_failure_is_owned_before_any_native_read(self):
        with self.lock.held():
            self.provider.base_scene=lambda:(_ for _ in ()).throw(OSError('Synthetic static HTTP failure'))
            owner=self.owner()
            with self.assertRaises(OSError):self.take(owner)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNone(owner.state['nativeStart'])
            self.assertEqual([],self.reads)
            with self.assertRaises(NativeUIError):self.take(self.owner())

    def test_guard_and_lock_prevent_acquisition_after_candidate_or_process_replacement(self):
        with self.lock.held():
            owner=self.owner();self.okay=False
            with self.assertRaises(NativeUIError):self.take(owner)
            self.assertIsNone(owner.store.read());self.assertEqual([],self.reads)
        self.okay=True
        with self.assertRaises(NativeUIError):self.owner()

    def test_completed_archive_stays_historical_after_deadline_and_originals_cannot_be_retimed(self):
        with self.lock.held():
            owner=self.owner();proof=self.take(owner);self.ms+=2000
            self.assertEqual(proof,owner.archive())
            with self.assertRaises(NativeUIError):owner.for_input()
            owner.state['originals']['ui']['sampleEpochMs']+=1
            with self.assertRaises(NativeUIError):owner.archive()
