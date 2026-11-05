"""Common normal actions through original automatic playback completion."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from adapters.pico4.audio_common_primary import AudioCommonPrimary1
from adapters.pico4.audio_common_files import PicoAudioCommonFiles1
from adapters.pico4.audio_common_flow import AudioCommonFlow1
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from self_tests.test_pico_audio_bundle_acquisition import AudioBundleAcquisitionTests


class CommonFourteenTests(unittest.TestCase):
    def test_actual_fourteen_common_phases_original_wavs_and_later_actor(self):
        self.fixture=AudioBundleAcquisitionTests();self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        pc=self.fixture.fixture;self.pc=pc;f=pc.f;actor=pc.actor;native=f.native
        primary=AudioCommonPrimary1(pc.owner);self.addCleanup(primary.close_host)
        files=PicoAudioCommonFiles1(actor);self.addCleanup(files.close_host)
        flow=AudioCommonFlow1(primary,files);self.flow=flow
        def witness():actor.publish();return f.journal.snapshot(f.run)
        journey=Journey('audio',f.run,f.source.fixture_url,invoke=flow.invoke,witness=witness,
            activate=lambda *_args:None,read_artifact=flow.read_artifact,image_policy={},continuity=lambda *_args:None,
            monotonic=lambda:native.clock,epoch_ms=native.epoch,sleep=native.sleep,report=lambda *_args:None)
        self.journey=journey
        initial=deepcopy(SCENARIOS['audio']['baseline']);phase=f.source.status();ticket=phase['activations'][-1]['ticket']
        journey.wait('owned-clean-baseline',ticket,native.epoch(),initial,[])
        for index,step in enumerate(SCENARIOS['audio']['steps']):
            ticket=f.activate(step['verb'],step['inputs']);barrier=native.epoch()
            if step['verb']=='await-completion':native.auto_complete=True
            if step['verb']=='close':
                def callbacks(seconds):
                    native.sleep(seconds)
                    for cycle,epoch in native.record_starts.items():
                        if cycle not in native.callback_events and native.epoch()-epoch>=30000:
                            native.callback_events[cycle]=dict(enteredEpochMs=native.epoch(),completedEpochMs=native.epoch(),retiredEpochMs=native.epoch(),retired=True)
                f.owner.child('page.prepare').settings.sleep=callbacks
            flow.invoke('feature.audio.act',dict(contractVersion=16,runId=f.run,fixtureUrl=f.source.fixture_url,
                ticket=ticket,verb=step['verb'],inputs=step['inputs']))
            if step['verb']=='record-start' and step['state']['recording']:journey.recorded_ticket=ticket
            observed=journey.wait(str(index+1)+'-'+step['verb'],ticket,barrier,step['state'],step['evidence'])
            native.auto_complete=False
        self.assertEqual(15,len(journey.phases));self.assertEqual(14,actor.recipe.state['cursor'])
        self.assertFalse(observed['state']['open']);self.assertEqual('cancelled',observed['state']['phase'])
        self.assertEqual([],observed['artifacts'])
        self.assertEqual(9,len(actor.state['jobs']));self.assertFalse(flow.failed)


if __name__=='__main__':unittest.main()
