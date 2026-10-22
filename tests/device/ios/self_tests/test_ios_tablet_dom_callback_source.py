"""No-build source guard and real host weak-token lifetime counterexample.

The Python closure models a retained native block; it does not execute WK/Qt.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
import weakref

ROOT=Path(__file__).resolve().parents[4]


class TabletDOMCallbackSourceTests(unittest.TestCase):
    def test_late_held_callback_remains_owned_after_timeout_and_body_return(self):
        header=(ROOT/'ios/web/IOSTabletWebDOMState.h').read_text()
        self.assertIn('std::weak_ptr<void> callbackCapture;',header)
        class Token:pass
        token=Token();capture=weakref.ref(token);packet=dict(status='pending',clockBefore=100000,clockAfter=100000);calls=[]
        def original_callback(retained=token):
            calls.append('actual modeled callback body')
            if packet['status']!='pending':return
            packet.update(status='ready',clockAfter=100010)
        native_holders=[original_callback];del token
        packet.update(status='unavailable',clockAfter=101500);original_terminal=deepcopy(packet)
        self.assertIsNotNone(capture())  # timeout is not capture death
        native_holders[0]();self.assertEqual(1,len(calls));self.assertEqual(original_terminal,packet)
        self.assertIsNotNone(capture())  # body return is not last block release
        del original_callback;native_holders.clear();self.assertIsNone(capture())
        self.assertEqual(original_terminal,packet)

    def test_actual_native_overlap_guard_uses_capture_weak_life_not_terminal_packet_status(self):
        source=(ROOT/'ios/web/IOSWebView.mm').read_text()
        body=source.split('QVariantMap IOSWebView::featureTabletWebDOMObservation(',1)[1].split('QVariantMap IOSWebView::featureWebDOMRequest(',1)[0]
        self.assertIn('old->issued && !old->callbackCapture.expired()',body)
        self.assertNotIn('old->issued && tablet_web_dom::pending(old)',body)
        self.assertIn('const auto callbackCapture=std::make_shared<int>(0);read->callbackCapture=callbackCapture;',body)
        callback=body.split('completionHandler:^(id result,NSError* error) {',1)[1]
        self.assertIn('(void)callbackCapture;',callback)
        self.assertIn('if (!tablet_web_dom::pending(read) || !tablet_web_dom::fresh(read)) { return; }',callback)


if __name__=='__main__':unittest.main()
