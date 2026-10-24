"""Actual Pico final native sender with explicit phase-source test seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_normal_scripts as normal_fixture
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_operations import LifecycleInputFence
from self_tests.test_pending_commit_owner import RUN


class LifecyclePendingPhaseTransportTests(unittest.TestCase):
    def setUp(self):
        fixture=normal_fixture.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.source,self.reader=fixture.pending_owner()
        self.native=fixture.instance._native_feature_observer(fixture.native.target)
        self.reader.send=self.native.send;self.checked=[]
        def refused():
            self.checked.append(True);raise NativeUIError('Actual final phase source changed')
        self.refused=refused

    def test_lifecycle_readonly_observe_keeps_candidate_guard_without_issued_input_phase(self):
        fence=object.__new__(LifecycleInputFence);fence.check=self.refused
        self.native.phase_fence=fence
        self.reader.read(RUN)
        self.assertEqual([],self.checked);self.assertEqual(['observe'],[row['operation'] for row in self.source.commands])
        self.fixture.native.digest='f'*64
        with self.assertRaises(RuntimeError):self.reader.read(RUN)
        self.assertEqual(1,len(self.source.commands));self.assertEqual([],self.checked)

    def test_lifecycle_mutation_checks_actual_final_sender_before_native_publication(self):
        self.reader.read(RUN)
        fence=object.__new__(LifecycleInputFence);fence.check=self.refused;self.native.phase_fence=fence
        with self.assertRaises(RuntimeError):self.reader.operate(RUN,'focus')
        self.assertEqual([True],self.checked);self.assertEqual(['observe'],[row['operation'] for row in self.source.commands])
        self.assertEqual(1,len(self.source.intents))

    def test_other_fence_readonly_behavior_is_not_relaxed(self):
        self.native.phase_fence=SimpleNamespace(check=self.refused)
        with self.assertRaises(RuntimeError):self.reader.read(RUN)
        self.assertEqual([True],self.checked);self.assertEqual([],self.source.commands)


if __name__=='__main__':unittest.main()
