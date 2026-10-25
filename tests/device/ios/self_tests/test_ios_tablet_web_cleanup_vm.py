"""Retained exact original old VM death is separate from a new stop boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_quiet import retired_vm
from self_tests.test_native_script_terminal import packet,MANAGER,CODE


def later(count=3):
    value=packet(count);value.update(commandId='ios-'+'1'*32,sequence=2,requestedEpochMs=21000,capturedEpochMs=21000);return value


class TabletWebCleanupVMTests(unittest.TestCase):
    def test_exact_already_retired_generation_keeps_its_original_pre_cleanup_clocks(self):
        before=packet();current=later();original=deepcopy(before['source']['events'])
        actual=retired_vm(before,current,MANAGER,CODE,after_epoch=20500)
        self.assertEqual(original,actual);self.assertLess(actual[-1]['capturedEpochMs'],20500)
        self.assertEqual(original,before['source']['events'])
    def test_same_shaped_new_manager_code_or_retimed_old_receipt_cannot_reuse_terminal(self):
        for fault in ('manager','code','generation','retime','source'):
            before=packet();current=later();manager=deepcopy(MANAGER);code=deepcopy(CODE)
            if fault=='manager':manager['instance']='0'*32
            elif fault=='code':code['sha256']='0'*64
            elif fault=='generation':manager['loadGeneration']+=1
            elif fault=='retime':current['source']['events'][-1]['capturedEpochMs']+=1
            else:current['source']['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):retired_vm(before,current,manager,code,after_epoch=20500)
    def test_inflight_generation_still_needs_actual_post_stop_shutdown_and_thread_exit(self):
        before=packet(1);current=later()
        with self.assertRaises(NativeUIError):retired_vm(before,current,MANAGER,CODE,after_epoch=20500)
        for event in current['source']['events'][1:]:event['capturedEpochMs']+=8500
        self.assertEqual(3,len(retired_vm(before,current,MANAGER,CODE,after_epoch=20500)))
        current['source']['events'].pop();current['source']['eventSequence']=2
        with self.assertRaises(NativeUIError):retired_vm(before,current,MANAGER,CODE,after_epoch=20500)


if __name__=='__main__':unittest.main()
