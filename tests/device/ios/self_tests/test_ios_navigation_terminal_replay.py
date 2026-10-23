"""Actual file/lease handoff; the initial live-seal decoder is an explicit model.

The separate whole tests must qualify its real source/PNG callback. These cases
check scoped reuse and mutations independently of app/native acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.navigation_process_end import NavigationProcessEnd
from ios.adapters.navigation_terminal_replay import checked
from ios.self_tests.navigation_end_fixture import EndBoundary


class NavigationTerminalReplayTests(unittest.TestCase):
    def setUp(self):self.h=EndBoundary(self)

    def test_one_actual_callback_per_scope_and_expired_handoff_cannot_be_used_again(self):
        h=self.h
        with h.flow.held():
            process=NavigationProcessEnd(h.terminal)
            with patch.object(h.terminal,'replay',wraps=h.terminal.replay) as replay:
                with checked(h.terminal,process.mutable()) as proof:
                    process.checked_terminal=proof
                    self.assertEqual(h.terminal.state['seal'],process.replay_terminal())
                    self.assertEqual(h.terminal.state['seal'],process.replay_terminal());self.assertEqual(1,replay.call_count)
                with self.assertRaises(NativeUIError):process.replay_terminal()
                process.checked_terminal=None;process.replay_terminal();self.assertEqual(2,replay.call_count)

    def test_changed_bytes_in_original_inode_are_refused_before_any_stop(self):
        h=self.h
        with h.flow.held(),self.assertRaises(NativeUIError):
            process=NavigationProcessEnd(h.terminal)
            with checked(h.terminal,process.mutable()) as proof:
                process.checked_terminal=proof;inode=h.payload.stat().st_ino;h.payload.write_bytes(h.payload_bytes+b'\n')
                self.assertEqual(inode,h.payload.stat().st_ino);process.replay_terminal()
        self.assertEqual(0,h.stops)

    def test_same_bytes_replaced_inode_is_refused_at_exit(self):
        h=self.h
        with h.flow.held(),self.assertRaises(NativeUIError):
            process=NavigationProcessEnd(h.terminal)
            with checked(h.terminal,process.mutable()):
                before=h.payload.stat().st_ino;h.payload.rename(h.payload.with_suffix('.retained-original'))
                h.payload.write_bytes(h.payload_bytes);h.payload.chmod(0o600);self.assertNotEqual(before,h.payload.stat().st_ino)
        self.assertEqual(0,h.stops)

    def test_unread_new_source_is_not_hidden_by_exact_read_membership(self):
        h=self.h
        with h.flow.held(),self.assertRaises(NativeUIError):
            process=NavigationProcessEnd(h.terminal)
            with checked(h.terminal,process.mutable()):
                PrivateFeatureState(h.root/'unread-foreign-original.json').write(dict(unexpected=True),None)
        self.assertEqual(0,h.stops)

    def test_another_terminal_cannot_borrow_the_checked_handoff(self):
        h=self.h;other=EndBoundary(self)
        with h.flow.held(),other.flow.held():
            a=NavigationProcessEnd(h.terminal);b=NavigationProcessEnd(other.terminal)
            with checked(h.terminal,a.mutable()) as proof:
                b.checked_terminal=proof
                with self.assertRaises(NativeUIError):b.replay_terminal()
        self.assertEqual(0,h.stops);self.assertEqual(0,other.stops)


if __name__=='__main__':unittest.main()
