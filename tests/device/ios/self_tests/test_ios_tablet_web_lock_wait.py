"""Real source-lock contention retains the original whole-call deadline."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from threading import Event,Thread,Timer
import time
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_feature import IOSTabletWebFeature


class TabletLockWaitTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.acquired,self.release=Event(),Event();self.error=[]
        def hold():
            try:
                with ScriptSourceLock(self.root/'script-feature-sources.lock').held():self.acquired.set();self.release.wait(2)
            except Exception as error:self.error.append(error)
        self.thread=Thread(target=hold);self.thread.start();self.assertTrue(self.acquired.wait(1));self.addCleanup(self.close)
    def close(self):self.release.set();self.thread.join(1);self.assertFalse(self.thread.is_alive());self.assertEqual([],self.error)
    def feature(self,clock,sleep):
        owner=object.__new__(IOSTabletWebFeature);owner.root=self.root;owner.monotonic=clock;owner.sleep=sleep
        owner.deadline=owner.last=None;owner.failed=False;return owner
    def test_actual_foreign_thread_lock_is_waited_out_without_renewing_whole_operation(self):
        owner=self.feature(time.monotonic,time.sleep);timer=Timer(.08,self.release.set);timer.start();self.addCleanup(timer.join)
        with owner.operation():
            deadline=owner.deadline
            with owner.locked(ScriptSourceLock(self.root/'script-feature-sources.lock',timeout=.01)) as actual:
                actual.assert_held();self.assertEqual(deadline,owner.deadline)
    def test_expired_original_budget_cannot_yield_or_bypass_a_foreign_lock(self):
        clock=[0.];sleeps=[]
        def elapsed(seconds):sleeps.append(seconds);clock[0]=60.
        owner=self.feature(lambda:clock[0],elapsed)
        with self.assertRaises(NativeUIError),owner.operation():
            with owner.locked(ScriptSourceLock(self.root/'script-feature-sources.lock',timeout=.01)):
                self.fail('Expired budget acquired the foreign lock')
        self.assertTrue(sleeps);self.assertFalse(self.release.is_set())


if __name__=='__main__':unittest.main()
