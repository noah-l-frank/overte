"""Actual Common baseline/open using new original primary source bundles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from adapters.pico4.audio_common_primary import AudioCommonPrimary1
from adapters.normal_ui import NativeUIError
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import projection
from self_tests.test_pico_audio_bundle_acquisition import AudioBundleAcquisitionTests


class PrimaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AudioBundleAcquisitionTests();self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        self.f=self.fixture.fixture;self.actor=self.f.actor
        self.primary=AudioCommonPrimary1(self.f.owner);self.addCleanup(self.primary.close_host)

    def call(self,after=0):
        return self.primary.invoke('feature.audio.observe',dict(contractVersion=16,runId=self.f.f.run,afterSequence=after))

    def test_actual_common_baseline_and_normal_open_have_advancing_original_samples(self):
        f=self.f.f;native=f.native
        def no_artifact(_name):raise AssertionError('No artifact is required by baseline/open')
        journey=Journey('audio',f.run,f.source.fixture_url,invoke=self.primary.invoke,
            witness=lambda:f.journal.snapshot(f.run),activate=lambda *_args:None,read_artifact=no_artifact,
            image_policy={},continuity=lambda *_args:None,monotonic=lambda:native.clock,
            epoch_ms=native.epoch,sleep=native.sleep,report=lambda *_args:None)
        phase=f.source.status();ticket=phase['activations'][-1]['ticket']
        initial=deepcopy(SCENARIOS['audio']['baseline'])
        first=journey.wait('owned-clean-baseline',ticket,native.epoch(),initial,[])
        ticket=f.activate('open');barrier=native.epoch()
        self.primary.invoke('feature.audio.act',dict(contractVersion=16,runId=f.run,fixtureUrl=f.source.fixture_url,
            ticket=ticket,verb='open',inputs={}))
        opened=journey.wait('normal-open',ticket,barrier,dict(initial,open=True),[])
        self.assertEqual(2,len(journey.phases));self.assertGreaterEqual(len(journey.samples),6)
        self.assertFalse(first['state']['open']);self.assertTrue(opened['state']['open'])
        primary_nonce=self.primary.state['value']['last']['command']['nativeNonce']
        published=self.actor.publish();self.assertEqual(projection('audio',opened['state']),published['facts'])
        self.assertNotEqual(primary_nonce,self.actor.observation_bundle.last_command['nativeNonce'])
        self.assertNotEqual(self.primary.credential,self.actor.raw_scope['actorCredentialSha256'])

    def test_foreign_run_refuses_before_getter_or_primary_state_mutation(self):
        before=deepcopy(self.primary.state);commands=len(self.fixture.model.commands)
        with self.assertRaises(NativeUIError):self.primary.invoke('feature.audio.observe',dict(contractVersion=16,runId='f'*32,afterSequence=0))
        self.assertEqual(before,self.primary.state);self.assertEqual(commands,len(self.fixture.model.commands))

    def test_identical_root_replacement_refuses_before_new_sdk_and_preserves_first_failure(self):
        self.call();path=self.primary.store.path;raw=path.read_bytes();other=path.with_name(path.name+'.replacement')
        other.write_bytes(raw);other.chmod(0o600);other.replace(path);commands=len(self.fixture.model.commands)
        with self.assertRaises((NativeUIError,ValueError)):self.call(1)
        self.assertTrue(self.primary.failed);self.assertIsNotNone(self.primary.failure);first=self.primary.failure
        with self.assertRaises((NativeUIError,ValueError)):self.call(1)
        self.assertIs(first,self.primary.failure);self.assertEqual(commands,len(self.fixture.model.commands))


if __name__=='__main__':unittest.main()
