"""Actual original ReturnPins dispatch; no device or complete Lifecycle proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest,sys
from unittest.mock import patch
from self_tests import test_pico_lifecycle_pending_return as fixture_module
from adapters.pico4 import lifecycle_pending_return as returns
from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED

class LifecycleReturnCloseDispatchTests(unittest.TestCase):
 def fixture(self):
  f=fixture_module.LifecyclePendingReturnPinsTests();f.setUp();self.addCleanup(f.doCleanups)
  with f.seams.lock.held():f.prepare()
  self.assertTrue(f.pins.partial);return f
 def counts(self,f):return f.raw.archive.state['reads'],len(f.seams.history.commands)
 def refused(self,f,calls,before,owners):
  self.assertEqual([],calls);self.assertFalse(f.pins.closed)
  self.assertIs(f.raw.return_slot,f.pins)
  self.assertTrue(any(owner is f.raw for _path,owner in UNRESOLVED))
  for owner in owners:
   self.assertFalse(owner.closed);owner.require(owner.fd)
  self.assertEqual(before,self.counts(f))
 def test_foreign_close_host_cannot_hide_live_original_data_ofds(self):
  f=self.fixture();calls=[];before=self.counts(f);owners=tuple(f.pins.partial)
  def foreign():calls.append(True);return True
  f.pins.close_host=foreign
  try:
   self.assertFalse(f.raw.close_host());self.refused(f,calls,before,owners)
  finally:del f.pins.close_host
 def test_foreign_delegated_inner_close_cannot_execute_or_authorize_success(self):
  f=self.fixture();calls=[];before=self.counts(f);owners=tuple(f.pins.partial)
  def foreign():calls.append(True);return True
  f.pins._close_host=foreign
  try:
   self.assertFalse(f.raw.close_host());self.refused(f,calls,before,owners)
  finally:del f.pins._close_host
 def test_foreign_failure_helper_getter_is_refused_before_any_original_close(self):
  f=self.fixture();calls=[];before=self.counts(f);owners=tuple(f.pins.partial)
  class Foreign:
   def __getattr__(self,name):calls.append(name);raise AssertionError('No foreign getter')
   def __call__(self,*args):calls.append('call');raise AssertionError('No foreign failure helper')
  f.pins._fail=Foreign()
  try:
   self.assertFalse(f.raw.close_host());self.refused(f,calls,before,owners)
  finally:del f.pins._fail
 def test_raw_class_descriptor_is_checked_before_it_can_bind(self):
  f=self.fixture();calls=[];before=self.counts(f);owners=tuple(f.pins.partial)
  class Foreign:
   def __get__(self,*args):calls.append('get');raise AssertionError('No foreign descriptor')
  with patch.object(returns.LifecyclePendingReturnPins,'close_host',Foreign()):
   self.assertFalse(f.raw.close_host());self.refused(f,calls,before,owners)
 def test_changed_original_inner_code_is_refused_before_it_executes(self):
  f=self.fixture();calls=[];before=self.counts(f);owners=tuple(f.pins.partial)
  original=returns.LifecyclePendingReturnPins.__dict__['_close_host'];code=original.__code__;previous=sys.getprofile()
  def foreign(self):return True
  def profile(frame,event,value):
   if event=='call' and frame.f_code is foreign.__code__:calls.append(True)
  try:
   original.__code__=foreign.__code__;sys.setprofile(profile)
   self.assertFalse(f.raw.close_host());self.refused(f,calls,before,owners)
  finally:original.__code__=code;sys.setprofile(previous)
 def test_actual_original_alias_closes_release_the_slot_and_keep_success_known(self):
  f=self.fixture();before=self.counts(f);owners=tuple(f.pins.partial)
  self.assertTrue(f.raw.close_host());self.assertTrue(f.pins.closed);self.assertFalse(f.pins.failed)
  self.assertIsNone(f.raw.return_slot);self.assertIsNone(f.raw._original_return_slot)
  self.assertTrue(f.pins._close_receipt)
  for owner in owners:
   self.assertTrue(owner.closed);self.assertFalse(owner.lost);self.assertEqual((-1,-1),(owner.fd,owner.anchor))
  self.assertEqual(before,self.counts(f))
