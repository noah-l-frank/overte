"""Final original clocks include copies and candidate guards; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from self_tests.test_pending_commit_owner import Boundary,RUN
from self_tests.test_pico_lifecycle_source import Boundary as UiBoundary


class LifecyclePendingFreshnessTests(unittest.TestCase):
    def test_original_pending_copy_native_jump_is_rejected_with_frozen_host_clock(self):
        boundary=Boundary();owner=boundary.owner();offset=0
        owner.clock_ms=lambda:boundary.epoch()+offset
        def late(value,*args,**kwargs):
            nonlocal offset
            result=deepcopy(value,*args,**kwargs)
            if type(value) is dict and 'pendingCommitOwnerVersion' in value:offset=2000
            return result
        with patch('adapters.pending_commit_owner.deepcopy',side_effect=late),self.assertRaises(NativeUIError):owner.read(RUN)
        self.assertEqual(0,boundary.clock);self.assertIsNone(owner.last);self.assertEqual(1,len(boundary.commands))

    def test_original_pending_final_candidate_guard_cannot_hide_native_jump(self):
        boundary=Boundary();owner=boundary.owner();guards=0;offset=0
        def guard():
            nonlocal guards,offset
            guards+=1
            if guards==3:offset=2000
            return True
        owner.guard=guard;owner.clock_ms=lambda:boundary.epoch()+offset
        with self.assertRaises(NativeUIError):owner.read(RUN)
        self.assertEqual(0,boundary.clock);self.assertIsNone(owner.last)

    def test_original_ui_copy_native_jump_is_rejected_before_source_admission(self):
        boundary=UiBoundary();source=boundary.source();offset=0;source.clock_ms=lambda:20000+offset
        def late(value,*args,**kwargs):
            nonlocal offset
            result=deepcopy(value,*args,**kwargs)
            if type(value) is dict and 'lifecycleUiVersion' in value:offset=2000
            return result
        with patch('adapters.pico4.lifecycle_source.deepcopy',side_effect=late),self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertIsNone(source.previous);self.assertIsNone(source.last_raw);self.assertEqual(0,boundary.clock)


if __name__=='__main__':unittest.main()
