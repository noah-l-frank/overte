"""Independent original native input receipts under deliberate host clock skew."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters import normal_input
from ios.self_tests.test_ios_normal_input import Boundary
from adapters.normal_ui import NativeUIError


class IOSNativeInputClockTests(unittest.TestCase):
    def boundary(self,status_epoch):
        source=Boundary();original=source.post
        def post(request,timeout):
            value=original(request,timeout)
            for key in ('observation','status'):
                if key in source.receipt:source.receipt[key]['sampleEpochMs']=20000 if key=='observation' else status_epoch
            return value
        native=normal_input.NativeInput(source,'owned-session',source.target,source.process,
            monotonic=source.tick,sleep=lambda _:None,native_epoch_ms=lambda:20000)
        return source,native,post

    def test_original_native_receipt_uses_separate_native_clock_for_capture_and_delivery(self):
        source,native,post=self.boundary(20000)
        with patch.object(normal_input,'urlopen',post),patch.object(normal_input.time,'time',return_value=1000000):
            self.assertEqual({'performed':True},native.edit('replace','actual input'))
        self.assertEqual(['observe','edit'],[row['operation'] for row in source.requests])

    def test_stale_or_future_original_receipt_is_not_retimed_or_resent(self):
        for epoch in (18000,21000):
            source,native,post=self.boundary(epoch)
            with patch.object(normal_input,'urlopen',post),self.assertRaises(NativeUIError):native.edit('replace','actual input')
            self.assertEqual(['observe','edit'],[row['operation'] for row in source.requests])


if __name__=='__main__':unittest.main()
