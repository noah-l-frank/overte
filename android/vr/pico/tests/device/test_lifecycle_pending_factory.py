"""Original Pico binding guards; native/SDK boundaries are explicit fixtures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_normal_scripts import PicoNormalScriptsTests
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.test_pico_lifecycle_source import RUN


class LifecyclePendingFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native

    def test_original_pico_guard_retains_owner_manifest_and_orphan_children_independently(self):
        store=self.adapter._lifecycle_world_store(self.native.target);root=store.path.parent
        self.assertFalse(self.adapter._lifecycle_pending_owned(self.native.target))
        for name in ('lifecycle-pending-owner.json','lifecycle-pending-originals.json','lifecycle-pending-originals.json.frame-000.json'):
            with self.subTest(name=name):
                candidate=PrivateFeatureState(root/name);candidate.write({'unresolved':'original-lifecycle-owner'},None)
                self.assertTrue(self.adapter._lifecycle_pending_owned(self.native.target));self.assertIsNotNone(candidate.read())
                # Test fixture only: remove this deliberately unowned sentinel
                # before testing the next disjoint source of responsibility.
                candidate.path.unlink()
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_actual_pending_factory_refuses_caller_world_before_any_script_or_native_input(self):
        with self.assertRaises(ValueError):self.adapter._lifecycle_pending_owner(self.native.target,RUN,world=SimpleNamespace())
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)


if __name__=='__main__':unittest.main()
