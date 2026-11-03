"""Actual host ownership files with explicitly modeled original phase metadata.

Seven selected counter cases; no SDK, native compilation, microphone, hardware,
playback, peer or acoustic qualification. Existing owner10 remains separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.self_tests.test_ios_audio_recorded_owner import Model
from ios.self_tests.test_ios_audio_passive_owner import AudioPassiveOwnerTests,PassiveBoundary


class PhaseLifecycleModel(Model):
    """Only the declared fixture producer differs from the original model."""
    def __init__(self):
        super().__init__();self.fixture_instance='3'*32;self.fixture_active=True;self.retired_epoch=None
    def retire_fixture(self):
        self.fixture_active=False;self.retired_epoch=self.epoch()
    def client(self):
        original=super().client();outer=self
        class PhaseLifecycleBoundary(Client):
            def request(self,*args,**kwargs):
                packet=original.request(*args,**kwargs)
                packet.update(instance=outer.fixture_instance,active=outer.fixture_active,retiredEpochMs=outer.retired_epoch)
                return packet
        return PhaseLifecycleBoundary(original.url,original.token)


class AudioPassivePhaseContinuityTests(unittest.TestCase):
    # Reuse real file/lock/Source construction without inheriting owner10 tests.
    owner=AudioPassiveOwnerTests.owner
    begin=AudioPassiveOwnerTests.begin
    def setUp(self):
        AudioPassiveOwnerTests.setUp(self)
        self.m=PhaseLifecycleModel();self.f.model=self.m;self.boundary=PassiveBoundary(self.m)
    def originals(self):
        return {path:(path.stat().st_ino,path.read_bytes()) for path in self.root.iterdir()}
    def reject_before_native(self,call):
        with self.owner() as owner:
            revisions=deepcopy(owner.state['streams']);commands=deepcopy(self.boundary.commands);before=self.originals()
            with self.assertRaises((ValueError,NativeUIError)):call(owner)
            self.assertEqual(revisions,owner.state['streams']);self.assertEqual(commands,self.boundary.commands)
            self.assertEqual(before,self.originals())
    def test_owned_capture_can_retire_after_original_fixture_inactive_with_distinct_absence(self):
        self.begin()
        with self.owner() as owner:wave=owner.capture()['wav']
        self.m.retire_fixture()
        with self.owner() as owner:
            result=owner.retire();self.assertTrue(result['retired']);self.assertFalse(result['nativeQualified'])
            self.assertEqual(wave,owner.snapshot()['wav'])
            release=next(frame for frame in owner.journals['proofs'].restore() if frame['kind']=='reply'
                and frame['packet']['operation']=='release')
            absence=owner.proof(result['absence'])
            self.assertFalse(release['phaseBefore']['active']);self.assertFalse(absence['phaseAfter']['active'])
            self.assertEqual(self.m.retired_epoch,absence['phaseAfter']['retiredEpochMs'])
            self.assertGreater(absence['packet']['sequence'],release['packet']['sequence'])
            state=absence['packet']['source'];self.assertFalse(state['state']['owned']);self.assertFalse(state['state']['watchdogOwned'])
            self.assertEqual(0,state['openOriginalFds']);self.assertEqual(0,state['originalBytes'])
            self.assertTrue(all(not row['exists'] for row in state['files']))
        self.assertEqual(1,self.boundary.count('start'));self.assertEqual(1,self.boundary.count('capture'))
        self.assertEqual(1,self.boundary.count('release'));self.assertEqual(1,self.boundary.count('files'))
    def test_lost_owned_release_after_fixture_retirement_recovers_without_resend(self):
        self.begin();self.m.retire_fixture();self.boundary.lose.add('release')
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.retire()
        self.boundary.lose.clear()
        with self.owner() as owner:self.assertTrue(owner.retire()['retired'])
        self.assertEqual(1,self.boundary.count('start'));self.assertEqual(1,self.boundary.count('release'))
        self.assertEqual(1,self.boundary.count('recover'));self.assertEqual(1,self.boundary.count('files'))
        self.assertFalse(self.boundary.owned);self.assertFalse(self.boundary.watchdog);self.assertFalse(self.boundary.files)
    def test_inactive_original_fixture_cannot_admit_new_start(self):
        self.m.retire_fixture();self.reject_before_native(lambda owner:owner.start(6))
        self.assertEqual([],self.boundary.commands)
    def test_foreign_fixture_instance_refuses_owned_cleanup_before_native_query(self):
        self.begin();self.m.fixture_instance='5'*32;self.m.retire_fixture()
        self.reject_before_native(lambda owner:owner.retire());self.assertTrue(self.boundary.owned)
    def test_dropped_original_activation_prefix_refuses_cleanup_before_native_query(self):
        self.begin();self.m.activations=[];self.m.retire_fixture()
        self.reject_before_native(lambda owner:owner.retire());self.assertTrue(self.boundary.owned)
    def test_retired_fixture_cannot_reactivate_during_reconstructed_start(self):
        self.begin();self.m.retire_fixture()
        with self.owner() as owner:self.assertTrue(owner.retire()['retired'])
        self.m.fixture_active=True;self.m.retired_epoch=None
        self.reject_before_native(lambda owner:owner.start(6));self.assertEqual(1,self.boundary.count('start'))
    def test_changed_retirement_epoch_refuses_later_control_before_native_query(self):
        self.begin();self.m.retire_fixture()
        with self.owner() as owner:self.assertTrue(owner.retire()['retired'])
        self.m.retired_epoch-=1
        self.reject_before_native(lambda owner:owner.control('files'));self.assertEqual(1,self.boundary.count('files'))


if __name__=='__main__':unittest.main()
