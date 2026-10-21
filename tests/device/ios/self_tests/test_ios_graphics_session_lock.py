"""Session handoff contention respects one budget and never replays a body."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from ios.adapters.graphics_session_retirement import IOSGraphicsSessionRetirement


class GraphicsSessionLockTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.value=object.__new__(IOSGraphicsSessionRetirement);self.now=0;self.entries=0;self.bodies=0
        self.value.lock=ScriptSourceLock(Path(temporary.name)/'sources.lock')
        def clock():need(self.now<60);return self.now
        self.value.flow=SimpleNamespace(clock=clock);self.value.sleep=lambda seconds:setattr(self,'now',self.now+seconds)
        self.original=self.value.lock.held

    def body(self):self.bodies+=1;self.value.lock.assert_held();return 'owned'

    def test_initial_actual_lock_contention_waits_then_enters_body_only_once(self):
        @contextmanager
        def contended():
            self.entries+=1
            if self.entries<=2:raise ScriptSourceBusy('Actual entry contention')
            with self.original():yield
        with patch.object(self.value.lock,'held',contended):self.assertEqual('owned',self.value.with_lock(self.body))
        self.assertEqual(3,self.entries);self.assertEqual(1,self.bodies);self.assertEqual(.05,self.now)

    def test_busy_from_inside_body_is_not_replayed(self):
        def body():self.bodies+=1;raise ScriptSourceBusy('Inner source unavailable')
        with self.assertRaises(ScriptSourceBusy):self.value.with_lock(body)
        self.assertEqual(1,self.bodies)

    def test_contended_entry_cannot_extend_whole_deadline(self):
        @contextmanager
        def contended():
            self.entries+=1;raise ScriptSourceBusy('Actual entry contention')
            yield
        self.value.sleep=lambda seconds:setattr(self,'now',self.now+10)
        with patch.object(self.value.lock,'held',contended),self.assertRaises(RuntimeError):self.value.with_lock(self.body)
        self.assertEqual(6,self.entries);self.assertEqual(0,self.bodies);self.assertEqual(60,self.now)


if __name__=='__main__':unittest.main()
