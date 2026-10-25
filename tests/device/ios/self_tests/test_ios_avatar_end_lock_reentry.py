"""Real flock reentry before the independent complete Avatar end decoder.

The decoder deliberately raises at its entry. These cases prove lock admission
and refusal only; none manufactures an end graph or qualifies terminal facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from ios.adapters.avatar_ended_archive import verify


class AtCompleteDecoder(RuntimeError):pass


class AvatarEndLockReentryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.run='a'*32;self.paths={role:self.root/role/'session.json' for role in ('primary','actor')}
        for path in self.paths.values():path.parent.mkdir(mode=0o700)
        self.adapter=SimpleNamespace(state_path=lambda target:self.paths[target]);self.terminal={}
        self.value=dict(iosAvatarFeatureVersion=1,role='primary',runId=self.run,selectors=dict(primary='primary',actor='actor'),
            artifactRoot=str(self.root/'artifacts'),imagePolicy={},fixtureUrl='https://127.0.0.1/feature-fixture/v1/runs/'+self.run+'/',payload=[])
        own=self.paths['primary'].with_name('ios-avatar-primary-feature.json')
        PrivateFeatureState(own).write(self.value,None)
        PrivateFeatureState(own.with_name('ios-avatar-primary-'+self.run+'-terminal.json')).write(self.terminal,None)
        self.locks={role:ScriptSourceLock(path.with_name('script-feature-sources.lock')) for role,path in self.paths.items()}

    def held(self):
        stack=ExitStack()
        for role in ('actor','primary'):stack.enter_context(self.locks[role].held())
        return stack

    def test_exact_current_lock_instances_reenter_without_a_second_flock_or_inode_write(self):
        with self.held():
            before={role:(lock.path.stat().st_dev,lock.path.stat().st_ino,lock.path.read_bytes()) for role,lock in self.locks.items()}
            with patch('ios.adapters.avatar_ended_archive.IOSAvatarFeature.archive',side_effect=AtCompleteDecoder('actual decoder entry')) as decoder:
                # ScriptSourceLock retains its closed exception boundary.
                with self.assertRaises(NativeUIError):
                    verify(self.adapter,'primary',self.value,self.terminal,held_locks=self.locks)
                self.assertEqual(1,decoder.call_count)
            for role,lock in self.locks.items():
                lock.assert_held();self.assertEqual(before[role],(lock.path.stat().st_dev,lock.path.stat().st_ino,lock.path.read_bytes()))

    def test_default_independent_reader_never_bypasses_an_existing_exclusive_owner(self):
        with self.held(),patch('ios.adapters.avatar_ended_archive.IOSAvatarFeature.archive') as decoder:
            with self.assertRaises(ScriptSourceBusy):verify(self.adapter,'primary',self.value,self.terminal)
            decoder.assert_not_called()

    def test_unheld_or_foreign_lock_cannot_create_a_missing_inode_or_reach_decoder(self):
        with patch('ios.adapters.avatar_ended_archive.IOSAvatarFeature.archive') as decoder:
            with self.assertRaises(NativeUIError):verify(self.adapter,'primary',self.value,self.terminal,held_locks=self.locks)
            self.assertFalse(any(lock.path.exists() for lock in self.locks.values()));decoder.assert_not_called()
            with self.held():
                changed=dict(self.locks);changed['actor']=self.locks['primary']
                with self.assertRaises(NativeUIError):verify(self.adapter,'primary',self.value,self.terminal,held_locks=changed)
                decoder.assert_not_called()


if __name__=='__main__':unittest.main()
