"""Actual host weak capture models at the Tablet live-quiet composition seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_quiet import bridge_drained
from ios.self_tests.test_ios_web_script_emissions import Emitter
from ios.self_tests.test_ios_tablet_web_source import packet


class TabletBridgeDrainTests(unittest.TestCase):
    def test_actual_returned_callback_with_retained_capture_blocks_until_real_weak_expiry(self):
        native=Emitter();call,queue,capture=native.good()
        frame=dict(ledger=packet(),emitter=native.snapshot());before=deepcopy(frame)
        with self.assertRaises(NativeUIError):bridge_drained(frame,[dict(profile=native.buttons.profile())])
        self.assertEqual(before,frame);self.assertIsNotNone(queue['returned'])
        del capture;gc.collect();frame['emitter']=native.snapshot()
        bridge_drained(frame,[dict(profile=native.buttons.profile())])
        self.assertFalse(frame['emitter']['queues'][0]['captureAlive'])
    def test_real_canceled_receiver_capture_expires_without_inventing_a_callback_body(self):
        native=Emitter();call=native.api();queue,capture=native.queue(call);native.leave(call)
        with self.assertRaises(NativeUIError):bridge_drained(dict(ledger=packet(),emitter=native.snapshot()),[dict(profile=native.buttons.profile())])
        del capture;gc.collect();current=native.snapshot()
        bridge_drained(dict(ledger=packet(),emitter=current),[dict(profile=native.buttons.profile())])
        self.assertIsNone(current['queues'][0]['entered']);self.assertIsNone(current['queues'][0]['returned'])
    def test_actual_pending_native_callback_and_foreign_emitter_cannot_qualify_quiet(self):
        native=Emitter();call,queue,capture=native.good();del capture;gc.collect()
        clean=dict(ledger=packet(),emitter=native.snapshot());profile=[dict(profile=native.buttons.profile())]
        bridge_drained(clean,profile)
        for fault in ('callback','pid','run'):
            changed=deepcopy(clean)
            if fault=='callback':
                changed['ledger']['events']=changed['ledger']['events'][:4];changed['ledger']['eventSequence']=4
            elif fault=='pid':changed['emitter']['processId']+=1
            else:changed['emitter']['runId']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):bridge_drained(changed,profile)


if __name__=='__main__':unittest.main()
