"""Actual native/file/PNG/input originals; native/Qt/GPU producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.retirement_receipts import web_scene
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.self_tests.test_ios_emote_rooted_retirement import RootedRetirementCompositionTests


class RootedSceneRetirementTests(unittest.TestCase):
    def setUp(self):
        self.f=RootedRetirementCompositionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=IOSEmoteRootedSceneRetirement(self.f.keyed)

    def test_actual_held_public_and_existing_scene_stage_keep_original_times_and_cannot_publish_primary_as_actor(self):
        f=self.f;raw=f.keyed.derive(f.keyed_ref);value=self.owner.read(f.keyed_ref)
        self.assertEqual(raw['public']['state'],value['public']['state'])
        self.assertEqual(raw['public']['capturedEpochMs'],value['public']['capturedEpochMs'])
        self.assertEqual(raw['public']['sequence'],value['public']['sequence'])
        self.assertEqual([r['resource'] for r in raw['held']],value['public']['resources'])
        self.assertEqual(['native-process-resources'],value['scene']['remaining'])
        self.assertEqual(value['scene'],web_scene(value['scene'],f.keyed.run,value['public']['sequence']))
        self.assertLessEqual(value['acquisition']['hostBeforeEpochMs'],raw['acquisition']['hostBeforeEpochMs'])
        self.assertEqual(value['acquisition']['hostAfterEpochMs'],raw['acquisition']['hostAfterEpochMs'])
        domain=f.f.domain;history=len(domain.history);actions=list(domain.io.actions)
        files={p:(p.stat().st_ino,p.read_bytes()) for p in f.f.root.rglob('*') if p.is_file()}
        self.assertEqual(value,self.owner.read(f.keyed_ref))
        with self.assertRaises(NativeUIError):self.owner.actor_original(f.keyed_ref)
        self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in f.f.root.rglob('*') if p.is_file()})

    def test_missing_actual_native_original_cannot_be_hidden_by_previously_derived_holders(self):
        f=self.f;self.owner.read(f.keyed_ref);domain=f.f.domain;history=len(domain.history)
        f.f.native.record_store(f.f.native_reference['index']).path.unlink()
        with self.assertRaises((NativeUIError,FileNotFoundError)):self.owner.read(f.keyed_ref)
        self.assertEqual(history,len(domain.history))


if __name__=='__main__':unittest.main()
