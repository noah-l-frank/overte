"""Composed original Tablet tail over actual HTTP/AFC and private file owners.

Native producers and distinct boundary clocks are explicit models. The tests
prove source/ownership composition, not device timing or native execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import inspect,quiet
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary


class TabletWebTailTests(unittest.TestCase):
    def setUp(self):self.boundary=TabletWholeBoundary(self);self.tail=TabletWebTail(self.boundary.runtime)
    def capture(self):return self.tail.read(self.tail.capture([]))
    def test_actual_whole_original_query_bracket_unused_quiet_and_historical_reconstruction(self):
        before=self.capture();stop=self.capture();frames=[]
        for _ in range(3):self.boundary.sleep(1.6);frames.append(self.capture())
        value=quiet(before,stop,frames,[])
        self.assertEqual([],value['proof']['heldResources']);self.assertGreaterEqual(value['hostAfterMonotonic']-value['hostBeforeMonotonic'],3)
        current=TabletWebTail(self.boundary.runtime,historical=True);self.assertEqual(5,len(current.frames))
        self.assertEqual(frames[-1],current.read(current.state['records'][-1]))
        self.assertFalse(any(query['action']=='feature-script-files' for query in self.boundary.commands))
        self.assertEqual(0,len(self.boundary.journal.snapshot(self.boundary.source.run)['entries']))
    def test_acquisition_time_cannot_substitute_for_actual_native_and_host_quiet(self):
        before=self.capture();stop=self.capture();frames=[self.capture() for _ in range(3)]
        with self.assertRaises(NativeUIError):quiet(before,stop,frames,[])
        self.assertTrue(all(frame['row']['status']=='returned' for frame in frames))
    def test_lost_actual_aux_send_retains_source_history_and_cannot_retry_tail(self):
        self.boundary.lost='feature-ios-pointer-state'
        with self.assertRaises((NativeUIError,OSError)):self.tail.capture([])
        count=len(self.boundary.commands);rebuilt=TabletWebTail(self.boundary.runtime);self.assertTrue(rebuilt.blocked)
        self.assertIsNotNone(rebuilt.state['pending']['nativeStart']);self.assertIn('keys',rebuilt.state['pending']['queries'])
        with self.assertRaises(NativeUIError):rebuilt.capture([])
        self.assertEqual(count,len(self.boundary.commands))
        pointer=self.boundary.runtime.auxiliary('pointer');pointer.history()
        self.assertTrue(pointer.blocked);self.assertEqual('failed',pointer.state['pending']['status'])
        self.assertEqual('feature-ios-pointer-state',pointer.state['pending']['query']['action'])
        self.assertFalse(pointer.state['pending']['sendReturned']);self.assertFalse(pointer.state['pending']['raws'])
        self.assertEqual(count,len(self.boundary.commands))


if __name__=='__main__':unittest.main()
