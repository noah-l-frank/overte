"""Actual Actor coordinator/ledger/original owners with raw producer models.

No SDK, native compilation, device, microphone, cue or acoustic projection is
exercised. Original host files and typed archives are actual production code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.audio_passive_actor import IOSAudioPassiveActor,lease_id
from ios.self_tests.test_ios_audio_passive_owner import PassiveBoundary
from ios.self_tests.test_ios_audio_passive_phase_continuity import PhaseLifecycleModel
from ios.self_tests.test_ios_audio_passive_runtime import RuntimeModel
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,RUN
import unittest


class AudioPassiveActorCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.m=PhaseLifecycleModel();self.f.model=self.m;self.ticket=self.m.ticket
        self.root=self.f.root/'passive-artifacts';self.root.mkdir(mode=0o700)
        self.boundary=PassiveBoundary(self.m,lease=lease_id(RUN,self.ticket));self.runtime=RuntimeModel(self.f,self.boundary)
        self.actor=self.make_actor()
    def make_actor(self):
        m=self.m
        return IOSAudioPassiveActor(self.runtime,'actor',RUN,self.root,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
    def census(self):
        return {path:(path.stat().st_ino,path.read_bytes()) for path in self.root.rglob('*') if path.is_file()}
    def test_original_native_birth_is_only_order_cue_and_ready_performs_no_fresh_source_or_native_query(self):
        value=self.actor.arm(self.ticket);self.assertIsNotNone(value['birth']);self.assertEqual(lease_id(RUN,self.ticket),value['leaseId'])
        before=self.census();commands=deepcopy(self.boundary.commands);sources=self.runtime.calls
        self.boundary.block=True;ready=self.actor.ready(self.ticket)
        self.assertEqual(value,ready);self.assertEqual(commands,self.boundary.commands);self.assertEqual(sources,self.runtime.calls);self.assertEqual(before,self.census())
        self.assertFalse(ready['acousticQualified']);self.assertFalse(ready['physicalADCQualified']);self.assertFalse(ready['peerQualified'])
        # The arm return releases the real SDK lock before Primary ordinary
        # recording input could be admitted by the independent coordinator.
        with ScriptSourceLock(self.f.lock.path,timeout=.01).held():pass
        self.boundary.block=False
        with self.actor.owner(value['leaseId']) as owner:owner.retire()
    def test_host_wait_never_claims_native_completion_then_original_capture_and_absence_are_measured(self):
        value=self.actor.step();self.assertIsNotNone(value['birth']);commands=deepcopy(self.boundary.commands);sources=self.runtime.calls
        waiting=self.actor.step();self.assertIsNone(waiting['snapshot']);self.assertEqual(commands,self.boundary.commands);self.assertEqual(sources,self.runtime.calls)
        self.boundary.finish();result=self.actor.step();self.assertEqual('retired',result['phase']);self.assertIsNotNone(result['snapshot']);self.assertIsNotNone(result['absence'])
        self.assertEqual(1,self.boundary.count('start'));self.assertEqual(1,self.boundary.count('capture'));self.assertEqual(1,self.boundary.count('release'));self.assertEqual(1,self.boundary.count('files'))
        before=self.census();commands=deepcopy(self.boundary.commands);sources=self.runtime.calls;self.boundary.block=True
        original=self.actor.original(self.ticket);self.assertEqual(128044,len(original['wav']))
        self.assertEqual(result['snapshot'],original['handoff']['snapshot']);self.assertEqual(result['leaseId'],original['native']['leaseId'])
        self.assertEqual(commands,self.boundary.commands);self.assertEqual(sources,self.runtime.calls);self.assertEqual(before,self.census())
        self.assertFalse(original['native']['source']['physicalADCQualified']);self.assertFalse(original['handoff']['acousticQualified'])
    def test_lost_native_start_return_reconstructs_actual_ledger_and_resolves_original_birth_without_second_start(self):
        self.boundary.lose.add('start')
        with self.assertRaises(NativeUIError):self.actor.arm(self.ticket)
        self.boundary.lose.clear();self.actor=self.make_actor();ready=self.actor.arm(self.ticket)
        self.assertIsNotNone(ready['birth']);self.assertEqual(1,self.boundary.count('start'));self.assertEqual(1,self.boundary.count('observe'))
        with self.actor.owner(ready['leaseId']) as owner:self.assertTrue(owner.retire()['retired'])
    def test_original_fixture_retirement_cleans_owned_actor_resources_without_creating_capture_or_an_acoustic_artifact(self):
        ready=self.actor.arm(self.ticket);self.m.retire_fixture();result=self.actor.step()
        self.assertEqual('retired',result['phase']);self.assertIsNone(result['snapshot']);self.assertIsNotNone(result['absence'])
        self.assertEqual(1,self.boundary.count('start'));self.assertEqual(0,self.boundary.count('capture'));self.assertEqual(1,self.boundary.count('release'));self.assertEqual(1,self.boundary.count('files'))
        self.assertFalse(self.boundary.owned);self.assertFalse(self.boundary.watchdog);self.assertFalse(self.boundary.files)
        with self.assertRaises(NativeUIError):self.actor.original(self.ticket)
    def test_lost_initial_empty_ledger_save_resumes_original_scope_before_any_native_allocation(self):
        from unittest.mock import patch
        from ios.adapters.audio_passive_runtime import PassiveSDKLedger
        original=PassiveSDKLedger.save;lost=[]
        def after_commit(ledger):
            result=original(ledger)
            if not ledger.rows and not lost:
                lost.append(deepcopy(ledger.previous));raise OSError('Declared lost return after actual initial empty ledger save')
            return result
        with patch.object(PassiveSDKLedger,'save',after_commit),self.assertRaises(OSError):self.actor.arm(self.ticket)
        self.assertEqual(1,len(lost));self.assertEqual([],lost[0]['leases']);self.assertEqual([],self.boundary.commands)
        self.assertEqual([],list(self.root.iterdir()));self.actor=self.make_actor();ready=self.actor.step()
        self.assertIsNotNone(ready['birth']);self.assertEqual(1,self.boundary.count('start'))
        with self.actor.owner(ready['leaseId']) as owner:self.assertTrue(owner.retire()['retired'])
    def test_foreign_canonical_sdk_binding_after_arm_cannot_capture_release_or_reallocate_actor_microphone(self):
        self.actor.arm(self.ticket);self.boundary.finish();self.runtime.binding['generation']+=1;commands=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.actor.step()
        self.assertEqual(commands,self.boundary.commands);self.assertEqual(1,self.boundary.count('start'));self.assertEqual(0,self.boundary.count('capture'));self.assertEqual(0,self.boundary.count('release'))
        self.assertTrue(self.boundary.owned)


if __name__=='__main__':unittest.main()
