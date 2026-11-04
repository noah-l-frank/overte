"""Causal model timestamps across declared producer millisecond boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.navigation_arrival import pose_packet
from contracts import validate_probe_snapshot
from self_tests.test_navigation_arrival import Model,SCENE


class BrowserProbeClockTests(unittest.TestCase):
    def model(self):
        model=Model();self.addCleanup(model.close);self.epochs=[]
        def epoch():
            value=20000+len(self.epochs);self.epochs.append(value);return value
        model.epoch=epoch;return model

    def test_probe_closes_after_actual_motion_and_render_subobservations_across_millisecond_changes(self):
        model=self.model();probe=model.probe(0)
        validate_probe_snapshot(probe)
        self.assertEqual([20000,20001,20002],self.epochs)
        self.assertLessEqual(probe['nativeMotion']['sampleEpochMs'],probe['sampleEpochMs'])
        self.assertLessEqual(probe['render']['lastFrameEpochMs'],probe['sampleEpochMs'])
        self.assertEqual(self.epochs[-1],probe['sampleEpochMs'])

    def test_existing_original_pose_reader_accepts_producers_with_a_declared_advancing_epoch(self):
        model=self.model();arrival=model.arrival();first=arrival.read();second=arrival.read()
        self.assertEqual('A',pose_packet(second,model.run_id,model.binding,SCENE,model.epoch()))
        self.assertGreater(second['probe']['sampleSequence'],first['probe']['sampleSequence'])
        self.assertGreater(second['probe']['sampleEpochMs'],first['probe']['sampleEpochMs'])
        self.assertGreater(second['subject']['capturedEpochMs'],first['subject']['capturedEpochMs'])
        self.assertEqual(2,len(model.subject.commands))


if __name__=='__main__':unittest.main()
