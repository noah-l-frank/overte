"""Fresh modeled Script clocks must fit their original parent acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import emote_world
from ios.self_tests.test_ios_emote_marker_owner import Domain,RUN
from ios.self_tests.test_ios_emote_marker_measurements import frames


class MarkerWorldProducerClockTests(unittest.TestCase):
    def model(self):
        domain=Domain.__new__(Domain);domain.time=0.;domain.sequences=dict(world=0);domain.world_template=frames()[0]
        def advancing_epoch():
            domain.time+=.001;return Domain.epoch(domain)
        domain.epoch=advancing_epoch;return domain
    def test_each_actual_producer_clock_tick_keeps_child_inside_new_parent(self):
        domain=self.model();original=domain.world(RUN);script=original['source']['scriptOriginal']
        clocks=[original['clockBefore']['epochMs'],script['requestedEpochMs'],
            script['capturedEpochMs'],original['clockAfter']['epochMs']]
        self.assertEqual(sorted(clocks),clocks);self.assertEqual(4,len(set(clocks)))
        self.assertIs(original,emote_world.original(original))
    def test_next_original_preserves_earlier_bytes_and_validator_still_rejects_future_child(self):
        domain=self.model();first=domain.world(RUN);before=deepcopy(first);second=domain.world(RUN)
        query=dict(schemaVersion=1,commandId=second['requestId'],action=emote_world.ACTION,runId=RUN)
        emote_world.validate(second,query,31,previous=first);self.assertEqual(before,first)
        invalid=deepcopy(second);invalid['clockAfter']['epochMs']=invalid['source']['scriptOriginal']['capturedEpochMs']-1
        with self.assertRaises(NativeUIError):emote_world.original(invalid)


if __name__=='__main__':unittest.main()
