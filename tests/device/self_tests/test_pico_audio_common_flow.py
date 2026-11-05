"""Common baseline/open/mute with independent actual source queries and WAVs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.pico4.audio_common_primary import AudioCommonPrimary1
from adapters.pico4.audio_common_files import PicoAudioCommonFiles1
from adapters.pico4.audio_common_flow import AudioCommonFlow1
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from self_tests.test_pico_audio_bundle_acquisition import AudioBundleAcquisitionTests


class FlowTests(unittest.TestCase):
    def test_actual_common_open_mute_silence_and_independent_peer(self):
        fixture=AudioBundleAcquisitionTests();self.addCleanup(fixture.doCleanups);fixture.setUp()
        pc=fixture.fixture;f=pc.f;actor=pc.actor;native=f.native
        primary=AudioCommonPrimary1(pc.owner);self.addCleanup(primary.close_host)
        files=PicoAudioCommonFiles1(actor);self.addCleanup(files.close_host)
        flow=AudioCommonFlow1(primary,files)
        def witness():actor.publish();return f.journal.snapshot(f.run)
        journey=Journey('audio',f.run,f.source.fixture_url,invoke=flow.invoke,witness=witness,
            activate=lambda *_args:None,read_artifact=flow.read_artifact,image_policy={},continuity=lambda *_args:None,
            monotonic=lambda:native.clock,epoch_ms=native.epoch,sleep=native.sleep,report=lambda *_args:None)
        initial=deepcopy(SCENARIOS['audio']['baseline']);phase=f.source.status();ticket=phase['activations'][-1]['ticket']
        journey.wait('owned-clean-baseline',ticket,native.epoch(),initial,[])
        for verb,inputs,state,kinds in (
            ('open',{},dict(initial,open=True),[]),
            ('mute',dict(enabled=True),dict(initial,open=True,muted=True),['silence','peer'])):
            ticket=f.activate(verb,inputs);barrier=native.epoch()
            flow.invoke('feature.audio.act',dict(contractVersion=16,runId=f.run,fixtureUrl=f.source.fixture_url,
                ticket=ticket,verb=verb,inputs=inputs))
            observed=journey.wait('normal-'+verb,ticket,barrier,state,kinds)
        self.assertEqual(3,len(journey.phases));self.assertGreaterEqual(len(journey.samples),9)
        self.assertTrue(observed['state']['muted']);self.assertEqual('audio',observed['artifacts'][0]['kind'])
        self.assertGreater(journey.witness_sequence,0);self.assertEqual(2,pc.owner.recipe.state['cursor'])
        self.assertEqual(1,len(actor.state['jobs']));self.assertEqual(1,len(files.state['files']))
        self.assertFalse(flow.failed);self.assertFalse(files.failed)


if __name__=='__main__':unittest.main()
