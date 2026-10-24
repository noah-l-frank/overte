"""Original Pico binding guards; native/SDK boundaries are explicit fixtures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_normal_scripts as normal_fixture
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.test_pico_lifecycle_source import RUN


class LifecyclePendingFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=normal_fixture.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
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

    def test_actual_factory_reconstructs_original_world_background_and_pending_without_input(self):
        from self_tests.test_pico_lifecycle_pending import LifecyclePendingTests
        from adapters.token_script_ui import TokenScriptUI
        case=LifecyclePendingTests('test_original_create_chat_return_to_scripts_pending_replacement_attempt_release_and_quiet')
        case.setUp();self.addCleanup(case.doCleanups)
        world,background=case.world,case.background
        route=TokenScriptUI(type(case.owner.route.io)(),monotonic=lambda:case.native.clock,sleep=case.native.sleep)
        self.adapter._script_runtime=lambda _target:(route,lambda _after:None,world.binding)
        self.adapter._native_feature_observer=lambda _target:SimpleNamespace(send=case.boundary.send,
            clock_ms=case.native.epoch,guard=lambda:True,pid=world.pid,monotonic=lambda:case.native.clock,sleep=case.native.sleep)
        self.adapter._lifecycle_world_store=lambda *_args,**_kwargs:PrivateFeatureState(world.store.path)
        queries=len(case.boundary.commands)
        owner=self.adapter._lifecycle_pending_owner(self.native.target,RUN,source_lock=world.lock,world=world,background=background)
        self.assertIs(owner.world,world);self.assertIs(owner.background,background);self.assertIs(owner.lock,world.lock)
        self.assertIs(owner.route,route);self.assertEqual(case.owner.disk,owner.disk)
        self.assertEqual(queries,len(case.boundary.commands));self.assertEqual([],case.x_inputs);self.assertEqual([],case.normal_inputs)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
        original=owner.store.read();wrong=deepcopy(original)
        self.assertIn(original['binding']['generation'],(0,1))
        wrong['binding']['generation']=bool(original['binding']['generation'])
        owner.store.write(wrong,original);raw=owner.store.path.read_bytes()
        route=TokenScriptUI(type(case.owner.route.io)(),monotonic=lambda:case.native.clock,sleep=case.native.sleep)
        self.adapter._script_runtime=lambda _target:(route,lambda _after:None,world.binding)
        with self.assertRaises(ValueError):
            self.adapter._lifecycle_pending_owner(self.native.target,RUN,source_lock=world.lock,world=world,background=background)
        self.assertEqual(raw,owner.store.path.read_bytes());self.assertEqual(queries,len(case.boundary.commands))


if __name__=='__main__':unittest.main()
