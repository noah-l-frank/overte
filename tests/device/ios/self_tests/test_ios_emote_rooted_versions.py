"""Actual whole metadata/scene originals retain disjoint literal readers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_scene_operation import owner as scene_owner
from ios.adapters.emote_scene_proof import validate,rooted
from ios.self_tests.emote_rooted_whole_fixture import paired


class RootedVersionTests(unittest.TestCase):
    def test_literal_whole_and_actual_initial_scene_versions_cannot_be_relabelled_without_any_new_query(self):
        f=paired(self);flow=f.flow
        flow.observe(dict(contractVersion=16,runId=flow.run,afterSequence=0))
        queries=len(f.target.native.requests);history=len(f.target.domain.history)
        legacy=IOSEmoteFeature(f.runtime,flow.selector,flow.client,flow.run,flow.role,flow.root,flow.policy,
            actor_selector=flow.actor_selector,monotonic=flow.monotonic,epoch_ms=flow.epoch_ms,sleep=flow.sleep)
        legacy.lock=legacy.primary_lock=flow.lock
        with self.assertRaises(NativeUIError):
            with legacy.held():legacy.load()
        with flow.held():
            flow.load();parts=flow.components();gate=scene_owner(flow,parts)
            ready,_actual=gate.original(gate.state['own'][0]);proof=ready['original']
            arguments=dict(stage=ready['stage'],root=flow.root,binding=flow.state['binding'],run=flow.run,role=flow.role,
                instance=flow.state['phaseInstance'],ticket=ready['ticket'],state_root=flow.store.path.parent,lock=flow.lock)
            self.assertEqual(2,proof['iosEmoteSceneProofVersion']);rooted(proof,**arguments)
            with self.assertRaises(NativeUIError):validate(proof,**arguments)
            for version in (1,True,3):
                wrong=deepcopy(proof);wrong['iosEmoteSceneProofVersion']=version
                with self.subTest(scene_version=version),self.assertRaises(NativeUIError):rooted(wrong,**arguments)
            previous=flow.store.read();wrong=deepcopy(previous);wrong['iosEmoteFeatureVersion']=1
            flow.store.write(wrong,previous)
            with self.assertRaises(NativeUIError):flow.load()
        self.assertEqual(queries,len(f.target.native.requests));self.assertEqual(history,len(f.target.domain.history))


if __name__=='__main__':unittest.main()
