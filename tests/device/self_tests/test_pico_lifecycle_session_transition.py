"""Cold first X and lost original return; no complete Lifecycle/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from self_tests.pico_lifecycle_pending3_diagnostic import LifecyclePending3Background5Tests

class LifecycleSessionReceiptTests(unittest.TestCase):
 def fixture(self):
  case=LifecyclePending3Background5Tests();case.BACKGROUND_QUIET_PERIOD=.75;case.PENDING_SESSION_RECEIPTS=True
  self.addCleanup(case.doCleanups);case.fixture();case.owner.prepare();return case
 def test_actual_first_x_original_outer_return_and_known_session_pairs(self):
  case=self.fixture();owner=case.owner
  # The original primary operations owner supplies an existing20s deadline.
  # That budget is not evidence of an active nested return-pins invocation.
  deadline=owner.world.monotonic()+20;owner.deadline=deadline
  owner.back();self.assertEqual(deadline,owner.deadline);self.assertEqual(0,owner._return_depth)
  self.assertEqual('home',owner.state['phase']);self.assertEqual(1,len(case.pending.x_inputs))
  self.assertEqual(1,len(owner.session_transitions));transition=owner.session_transitions[0]
  self.assertTrue(transition.committed);self.assertEqual(2,len(transition.close_receipts))
  self.assertTrue(transition.old.closed);self.assertTrue(transition.new.closed)
  self.assertIsNotNone(owner.return_pins)
  with owner.lock.held():
   owner.return_pins.verify_data();case.namespace.guard_lease();owner.close_return_pins()
  self.assertTrue(case.bank.close_host());self.assertTrue(case.namespace.close())
 def test_actual_session_save_then_lost_return_retains_old_pair_and_prevents_next_input(self):
  case=self.fixture();case.pending.lost='x'
  with self.assertRaises(NativeUIError):case.owner.back()
  self.assertEqual(1,len(case.pending.x_inputs))
  transition=case.owner.session_transitions[0]
  self.assertFalse(transition.committed);self.assertIsNotNone(transition.error)
  self.assertFalse(transition.old.closed);self.assertTrue(case.bank.failed)
  self.assertEqual(transition.value['nextSequence']+1,case.owner.world.session._load()['nextSequence'])
  count=len(case.pending.x_inputs);reads=case.bank.archive.state['reads']
  with self.assertRaises(NativeUIError):case.owner.back()
  self.assertEqual(count,len(case.pending.x_inputs));self.assertEqual(reads,case.bank.archive.state['reads'])
  self.assertFalse(case.bank.close_host())
