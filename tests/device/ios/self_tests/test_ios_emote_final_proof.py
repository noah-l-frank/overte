"""Fresh final native/Qt absence over genuine host-owned original archives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_final_proof import validate
from ios.adapters.emote_retirement_scope import refresh
from ios.self_tests import test_ios_emote_retirement as retirement_fixture


class FinalProofTests(unittest.TestCase):
    def setUp(self):
        self.fixture=retirement_fixture.RetirementTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.prior=self.fixture.sources.frames[-1]['clockJoin']['nativeAfter']
        self.fixture.owner().retain(self.fixture.original)
    def refresh(self):
        f=self.fixture;refresh(f.scope,clock=lambda:f.domain.time,sleep=f.domain.sleep,pointers=f.pointers)
        f.entities.capture()
    def proof(self):
        f=self.fixture;return validate(f.scope,f.entities,None,f.pointers,self.prior)
    def test_fresh_local_finalization_extends_original_history_and_pointer_end_without_new_inputs(self):
        f=self.fixture;operations=list(f.scope.state['operations']);self.refresh();f.pointers.capture()
        result=self.proof();self.assertGreater(result['sequence'],self.prior['sequence'])
        self.assertEqual(operations,f.scope.state['operations']);self.assertFalse(result['animation']['overrideActive'])
        self.assertEqual(self.prior['animation']['history']['callSequence'],result['animation']['history']['callSequence'])
    def test_an_old_pointer_snapshot_before_the_latest_entity_original_cannot_retire_metadata(self):
        self.refresh()
        with self.assertRaises(NativeUIError):self.proof()
    def test_later_actual_touch_contact_or_new_complete_input_prevents_final_quiet(self):
        self.refresh();f=self.fixture;f.qt.boundary.touch('touch-begin');f.pointers.capture()
        with self.assertRaises(NativeUIError):self.proof()
        f.qt.boundary.touch('touch-end');f.pointers.capture()
        with self.assertRaises(NativeUIError):self.proof()
        self.refresh();f.pointers.capture();self.assertTrue(self.proof())


if __name__=='__main__':unittest.main()
