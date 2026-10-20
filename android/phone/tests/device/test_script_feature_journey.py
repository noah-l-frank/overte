"""The unchanged full Script journey through the actual Phone facade.

Native/SDK sources are synthetic; HTTP delivery uses an owned loopback server.
This is host control verification, never native execution or device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_script_feature as model


class ScriptFullJourneyTests(unittest.TestCase):
    def test_complete_shared_v16_journey_uses_two_fresh_readers_and_original_http(self):
        f=model.ScriptFeatureTests('test_baseline_uses_independent_original_sources_no_stage_and_separate_actor_history')
        f.setUp();self.addCleanup(f.doCleanups)
        from feature_journeys.engine import Journey
        reports=[]
        def invoke(operation,fields):return getattr(f.primary,operation.rsplit('.',1)[1])(fields)
        def witness():f.actor.publish();return f.client.observe()
        journey=Journey('scripts',model.RUN,f.fixture,invoke=invoke,witness=witness,activate=f.client.activate,
            read_artifact=lambda _name:self.fail('Scripts has no byte artifact shortcut'),image_policy={},
            continuity=lambda *_args:None,monotonic=lambda:f.clock,epoch_ms=f.epoch,sleep=f.sleep,report=reports.append)
        journey.execute()
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(19,len(reports[-1]['phases'])-2)
        self.assertFalse(f.storage.root.exists());self.assertEqual(['stop','launch'],f.f.native.lifecycle_inputs)
        self.assertEqual(1,len(f.server.script_resources.snapshot(model.RUN)['responses']))
        # The independently observed final baseline is also sufficient for the
        # normal adapter-wide journal retirement path, before SDK teardown.
        self.assertEqual({'performed':True},f.primary.finalize())
        self.assertTrue(all(store.read() is None for store in f.primary._retirement_paths()))


if __name__=='__main__':unittest.main()
