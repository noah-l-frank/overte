"""A quiet suffix cannot hide an older actual listener still held alive."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_quiet import dialog_drained
from ios.self_tests.test_ios_script_dialogs import packet,events


class TabletCleanupDialogTests(unittest.TestCase):
    def test_listener_born_before_cleanup_baseline_still_needs_actual_return_and_destruction(self):
        for count in (1,2,3):
            before=packet(1,events()[:count]);current=packet(2,events()[:count])
            with self.subTest(count=count),self.assertRaises(NativeUIError):dialog_drained(before,current,[])
    def test_original_already_returned_destroyed_listener_keeps_unchanged_original_clocks(self):
        before=packet(1,events());current=packet(2,events())
        self.assertEqual([],dialog_drained(before,current,[]))
        self.assertEqual(before['source'],current['source'])
    def test_old_unrelated_complete_listener_does_not_supply_a_new_listener_return(self):
        before=packet(1,events());current=packet(2,events());extra=events()[:1]
        extra[0].update(dialogInstance='b'*32,eventSequence=5);current['source']['events']+=extra;current['source']['eventSequence']=5
        with self.assertRaises(NativeUIError):dialog_drained(before,current,[])
    def test_actual_completion_of_exact_baseline_listener_needs_no_new_born_event_or_retiming(self):
        for count in (1,2,3):
            before=packet(1,events()[:count]);original=deepcopy(before);current=packet(2,events())
            with self.subTest(count=count):self.assertEqual([],dialog_drained(before,current,[]))
            self.assertEqual(original,before);self.assertEqual(before['source']['events'],current['source']['events'][:count])
    def test_baseline_listener_cannot_return_a_foreign_unadmitted_manager(self):
        manager=dict(instance='c'*32,assigned=True,url='file:///private/foreign.js',loadGeneration=1,assignedEpochMs=20000)
        before=packet(1,events()[:1]);current=packet(2,events(manager=manager))
        with self.assertRaises(NativeUIError):dialog_drained(before,current,[])


if __name__=='__main__':unittest.main()
