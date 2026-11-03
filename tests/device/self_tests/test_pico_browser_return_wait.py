"""Actual kernel contention at the coordinator's passive Actor-return wait.

Only pending-root waiting is exercised. Candidate/native/Actor payloads are not
qualified by the declared owner facade used to reach that exact boundary.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_operation_owner import PicoBrowserOperationOwner
from adapters.script_journey.lock import ScriptSourceLock


class OriginalOwnerBoundary(Exception):pass

CHILD='''from pathlib import Path
import sys,time
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
root=Path(sys.argv[1]);lock=ScriptSourceLock(root/'sources.lock')
store=PrivateFeatureState(root/'pico-tablet-web-actor-return.json')
with lock.held():
 store.write(dict(phase='preparing'),None)
 print('held',flush=True)
 time.sleep(.3)
 if sys.argv[2]=='ready':store.write(dict(phase='ready'),dict(phase='preparing'))
 time.sleep(.025)
sys.stdin.buffer.readline()
'''


class BrowserReturnWaitTests(unittest.TestCase):
    def setup_owner(self,mode):
        temporary=tempfile.TemporaryDirectory(prefix='browser-return-wait-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700)
        process=subprocess.Popen([sys.executable,'-c',CHILD,str(root),mode],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def close():
            if process.poll() is None:process.stdin.write(b'exit\n');process.stdin.flush()
            stdout,stderr=process.communicate(timeout=3)
            self.assertEqual(0,process.returncode,stderr.decode());self.assertFalse(stdout)
            self.assertFalse(Path(f'/proc/{process.pid}').exists())
        self.addCleanup(close);self.assertEqual(b'held\n',process.stdout.readline())
        lock=ScriptSourceLock(root/'sources.lock',timeout=.05);calls=[]
        def guard():
            self.assertIsNone(process.poll())
        def native_owner():
            lock.assert_held();calls.append('original-owner');raise OriginalOwnerBoundary()
        owner=object.__new__(PicoBrowserOperationOwner)
        owner.common=SimpleNamespace(complete=True,failed=False);owner.actor_return=None
        owner.feature=SimpleNamespace(store=PrivateFeatureState(root/'feature.json'),lock=lock,owner=native_owner)
        owner.worker_owner=SimpleNamespace(guard=guard);owner.collect=lambda:None
        owner.control=guard
        return owner,lock,calls,root

    def test_pending_original_child_can_hold_source_lock_beyond_parent_lock_timeout(self):
        owner,lock,calls,root=self.setup_owner('ready');started=time.monotonic()
        with self.assertRaises(NativeUIError):owner.return_actor()
        self.assertGreaterEqual(time.monotonic()-started,.25)
        self.assertEqual(['original-owner'],calls);self.assertIsNone(lock._owner)
        self.assertEqual(dict(phase='ready'),PrivateFeatureState(root/'pico-tablet-web-actor-return.json').read())

    def test_original_deadline_stops_pending_wait_without_lock_or_native_owner(self):
        owner,lock,calls,root=self.setup_owner('pending');started=time.monotonic();entries=[]
        original=lock.held
        def held():entries.append(True);return original()
        lock.held=held
        def control():
            if time.monotonic()-started>=.15:raise NativeUIError('Original test deadline expired')
        owner.control=control
        with self.assertRaises(NativeUIError):owner.return_actor()
        self.assertFalse(entries);self.assertFalse(calls);self.assertIsNone(lock._owner)
        self.assertEqual(dict(phase='preparing'),PrivateFeatureState(root/'pico-tablet-web-actor-return.json').read())


if __name__=='__main__':unittest.main()
