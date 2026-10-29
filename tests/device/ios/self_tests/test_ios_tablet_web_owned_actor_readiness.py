"""Actual app original -> private Actor root readiness; no effect authority.

Existing readiness fixture explicitly models native birth/source and SDK.
Real owners/WAL/closed-copy/app files execute; no independent Actor process or
public26/current native/GPU/peer readiness is manufactured.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters import tablet_web_child_rotation as closed,tablet_web_rotation_fence as fence
from ios.adapters.tablet_web_app_readiness import ready,retain
from ios.self_tests import test_ios_tablet_web_app_readiness as existing


class TabletOwnedActorReadinessTests(unittest.TestCase):
    def setUp(self):
        self.f=existing.TabletAppReadinessTests();self.addCleanup(self.f.doCleanups);self.f.setUp()
        source=self.f.actor.observer.source;expected=fence.scope(source.binding,source.run,source.role,source.fixture,source.pid)
        value=closed.make(source);source.store.write(value,source.saved)
        def guard():closed.decode(source.store.read(),expected);return True
        def intent(kind,reference):
            previous=source.store.read();changed=closed.with_copy_intent(previous,kind,reference,expected);source.store.write(changed,previous)
        copies=OriginalFrameStore(source.root,source.binding,source.run,source.role,guard,intent,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=source.monotonic)
        copies.write(1,closed.copy_body(value,expected))
        self.actor=aggregate.open_owned(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,source.guard,
            epoch_ms=source.epoch_ms,monotonic=source.monotonic)
        self.f.actor.observer.source=self.actor
        self.header=source.store.path;self.header_pin=self.pin(self.header)

    @staticmethod
    def pin(path):
        info=path.stat();return info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,path.read_bytes()

    def assert_moved_original(self,before,path):
        after=self.pin(path)
        # The deliberate rename preserves bytes/inode/mtime; Linux advances ctime.
        self.assertEqual(before[:4]+before[5:],after[:4]+after[5:])
        self.assertGreaterEqual(after[4],before[4])

    def external(self):
        value=tempfile.TemporaryDirectory(prefix='tablet-actor-root-original-');self.addCleanup(value.cleanup)
        return Path(value.name)

    def test_actual_actor_original_retained_then_primary_private_ready_keeps_closed_parent_unchanged(self):
        self.assertFalse(ready(self.f.primary,[self.f.metadata]))
        actual=retain(self.f.actor,self.f.metadata,self.f.reference)
        self.assertTrue(ready(self.f.primary,[self.f.metadata]));self.assertNotIn('public',actual)
        self.assertNotIn('capturedEpochMs',actual);self.assertEqual(self.header_pin,self.pin(self.header));self.assertEqual([],self.f.calls)

    def test_missing_owned_actor_root_never_adopts_closed_Source3_or_repeats_query(self):
        retain(self.f.actor,self.f.metadata,self.f.reference)
        path=self.actor.store.path;before=self.pin(path);witness=self.external()/'owned-actor-root.original.json';path.rename(witness)
        with self.assertRaises(NativeUIError):ready(self.f.primary,[self.f.metadata])
        self.assert_moved_original(before,witness);self.assertFalse(path.exists());self.assertEqual([],self.f.calls)
        self.assertEqual(self.header_pin,self.pin(self.header))

    def test_samebytes_parent_inode_replacement_during_actual_app_original_read_refuses_private_ready(self):
        retain(self.f.actor,self.f.metadata,self.f.reference);raw=self.header.read_bytes();witness=self.external()/'actor-canonical-parent.original.json'
        original=OriginalFrameStore.read;changed=[]
        def actual(store,value):
            packet=original(store,value)
            if store.namespace=='tabletweb-app-origins' and store.role=='actor' and not changed:
                self.header.rename(witness);self.header.write_bytes(raw);self.header.chmod(0o600);changed.append(True)
            return packet
        with patch.object(OriginalFrameStore,'read',actual),self.assertRaises(NativeUIError):ready(self.f.primary,[self.f.metadata])
        self.assertEqual([True],changed);self.assert_moved_original(self.header_pin,witness)
        self.assertNotEqual(self.header_pin[1],self.header.stat().st_ino);self.assertEqual([],self.f.calls)


if __name__=='__main__':unittest.main()
