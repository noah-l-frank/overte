"""Fresh passive end preserves actual original quiet and interrupted ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_retirement_scope_end import extend
from ios.adapters.emote_retirement_scope import refresh
from ios.self_tests import test_ios_emote_pointers as fixture


class ScopeEndTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.PointerOwnerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.quiet();self.scope=self.fixture.scope;self.pointer=self.fixture.owner;self.domain=self.fixture.domain

    def test_actual_quiet_can_extend_to_a_fresh_end_without_normal_input(self):
        old=list(self.scope.state['quiet']);operations=list(self.scope.state['operations']);self.domain.sleep(2.)
        self.assertTrue(extend(self.scope,self.pointer));self.assertEqual(old,self.scope.state['quiet'][:-1])
        self.assertEqual(operations,self.scope.state['operations']);self.assertTrue(self.pointer.closed(self.scope))

    def test_completed_input_after_original_quiet_requires_a_new_quiet_interval(self):
        old=list(self.scope.state['quiet']);qt=self.fixture.qt.boundary
        qt.touch('touch-begin');qt.touch('touch-end')
        with self.assertRaises(NativeUIError):extend(self.scope,self.pointer)
        self.assertEqual(old,self.scope.state['quiet'])
        refresh(self.scope,clock=self.scope.monotonic,sleep=self.scope.sleep,pointers=self.pointer)
        self.assertTrue(extend(self.scope,self.pointer));self.assertTrue(self.pointer.closed(self.scope))

    def test_lost_fresh_end_preserves_reconstructable_released_scope_and_original_quiet(self):
        old=list(self.scope.state['quiet']);read=self.scope.web.read
        self.scope.web.read=lambda *_:(_ for _ in ()).throw(OSError('Lost fresh Web inventory'))
        with self.assertRaises(OSError):extend(self.scope,self.pointer)
        rebuilt=self.fixture.fixture.owner();self.assertEqual('released',rebuilt.state['phase']);self.assertEqual(old,rebuilt.state['quiet'])
        self.scope.web.read=read;self.assertTrue(extend(self.scope,self.pointer));self.assertTrue(self.pointer.closed(self.scope))


if __name__=='__main__':unittest.main()
