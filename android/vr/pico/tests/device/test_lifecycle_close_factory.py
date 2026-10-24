"""Actual Pico close factory and canonical retained-owner responsibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_normal_scripts as normal_fixture
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.test_pico_lifecycle_source import RUN


class LifecycleCloseFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=normal_fixture.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native

    def test_orphan_close_archive_prevents_generic_retirement_without_a_parent(self):
        root=self.adapter._lifecycle_world_store(self.native.target).path.parent
        self.assertFalse(self.adapter._lifecycle_close_owned(self.native.target))
        for name in ('lifecycle-close-owner.json','lifecycle-close-originals.json','lifecycle-close-originals.json.frame-000.json'):
            with self.subTest(name=name):
                candidate=PrivateFeatureState(root/name);candidate.write({'unresolved':'original-close-owner'},None)
                self.assertTrue(self.adapter._lifecycle_close_owned(self.native.target))
                self.assertIsNotNone(candidate.read())
                candidate.path.unlink()  # Disjoint deliberately unowned test sentinels only.
        orphan=PrivateFeatureState(root/'lifecycle-close-originals.json.frame-000.json')
        orphan.write({'unresolved':'original-close-owner'},None);original=orphan.path.read_bytes()
        with self.assertRaises(ValueError):self.adapter.cleanup(self.native.target)
        self.assertEqual(original,orphan.path.read_bytes());self.assertFalse(self.native.running)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_foreign_caller_is_refused_before_native_access_or_input(self):
        with patch.object(self.adapter,'_native_feature_observer',side_effect=AssertionError('Unexpected native access')):
            with self.assertRaises(ValueError):
                self.adapter._lifecycle_close_owner(self.native.target,RUN,pending=SimpleNamespace())
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_actual_factory_keeps_canonical_namespace_original_process_and_source_lock(self):
        from self_tests import test_pico_lifecycle_editor as editor_fixture
        from self_tests import test_pico_lifecycle_close as close_fixture
        # Construct the existing complete fixture in the actual binding's
        # canonical namespace; do not replace its source-lock validation.
        root=self.adapter._lifecycle_world_store(self.native.target).path.parent
        directories=SimpleNamespace(TemporaryDirectory=lambda **_kwargs:SimpleNamespace(name=str(root),cleanup=lambda:None))
        case=close_fixture.LifecycleCloseTests()
        with patch.object(editor_fixture,'tempfile',directories):case.setUp()
        self.addCleanup(case.doCleanups)
        pending,world=case.pending,case.world
        self.assertEqual(root,world.store.path.parent)
        self.adapter._native_feature_observer=lambda _target:SimpleNamespace(pid=world.pid,guard=lambda:True)
        self.adapter.require_pico_session_identity=lambda _target:world.binding['processIdentity']
        before=[len(source.commands) for source in (case.native.ui,case.native.axes,case.native.drive)]
        originals=deepcopy((pending.disk,world.disk));queries=len(case.fixture.boundary.commands)
        owner=self.adapter._lifecycle_close_owner(self.native.target,RUN,pending=pending)
        self.assertIs(owner.pending,pending);self.assertIs(owner.world,world);self.assertIs(owner.lock,world.lock)
        self.assertEqual(root/'lifecycle-close-owner.json',owner.store.path)
        self.assertIsNone(owner.disk);self.assertEqual(originals,(pending.disk,world.disk))
        self.assertEqual(before,[len(source.commands) for source in (case.native.ui,case.native.axes,case.native.drive)])
        self.assertEqual(queries,len(case.fixture.boundary.commands));self.assertEqual([],case.inputs)
        self.adapter.require_pico_session_identity=lambda _target:'124:foreign-process'
        with self.assertRaises(ValueError):self.adapter._lifecycle_close_owner(self.native.target,RUN,pending=pending)
        self.assertEqual(before,[len(source.commands) for source in (case.native.ui,case.native.axes,case.native.drive)])
        self.assertEqual([],case.inputs);self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)


if __name__=='__main__':unittest.main()
