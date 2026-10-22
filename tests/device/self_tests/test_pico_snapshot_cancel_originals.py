"""Bounded lossless Snapshot history, cold integrity and original SDK profiles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_platform import PicoSnapshotPlatform,profile
from adapters.script_journey.history import pack
from self_tests.test_pico_lifecycle_back import BINDING
from self_tests.test_pico_lifecycle_source import RUN


class SnapshotOriginalContainerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='snapshot-originals-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.path=self.root/'snapshot-cancel-originals.json';self.owner=self.make()
    def make(self):return SnapshotCancelOriginals(self.path,RUN,BINDING)
    def state(self,frames=None):return dict(frames=[] if frames is None else frames,replies=[],vm=None)
    def test_full_original_bundles_cross_flat_limit_and_cold_reconstruct_without_projection(self):
        rng=random.Random(215);state=self.state([dict(rawOriginal=[rng.random() for _ in range(1200)],index=index) for index in range(30)])
        with self.assertRaises(NativeUIError):pack([state])
        encoded=self.owner.encode(state);self.assertEqual(state,self.make().decode(encoded));pack([encoded])
        self.assertEqual(30,len(self.owner.values));self.assertEqual(encoded,self.owner.encode(state,host_only=True))
        with self.assertRaises(NativeUIError):self.owner.encode(self.state([dict(newOriginal=True)]),host_only=True)
        self.owner.verify();self.assertTrue(all(p.stat().st_size<=65536 and p.stat().st_mode&0o777==0o600 for p in self.root.iterdir()))
    def test_changed_missing_replaced_and_foreign_children_never_become_accepted_originals(self):
        for fault in ('missing','changed','same-bytes-new-inode','permissions','foreign'):
            with self.subTest(fault=fault):
                self.setUp();self.owner.encode(self.state([dict(actual='source')]))
                child=self.owner.history.store(0);before=child.read()
                if fault=='missing':child.path.unlink()
                elif fault=='permissions':child.path.chmod(0o644)
                else:
                    value=deepcopy(before)
                    if fault=='changed':value['transcript']=pack([dict(kind='frame',original=dict(actual='changed'))])
                    if fault=='foreign':value['scopeSha256']='f'*64
                    child.write(value,before)
                with self.assertRaises(NativeUIError):self.owner.verify()
                # A cold manifest binds exact bytes/scope. Same-byte replacement
                # is rejected by the warm original inode; no cold freshness or
                # new identity claim is inferred from this passive container.
                if fault!='same-bytes-new-inode':
                    with self.assertRaises(NativeUIError):self.make()
    def test_lost_manifest_and_deleted_root_leave_children_unresolved_without_adoption(self):
        write=self.owner.root.write;calls=0
        def lost(value,previous):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('Explicit original manifest loss')
            return write(value,previous)
        with patch.object(self.owner.root,'write',side_effect=lost),self.assertRaises(OSError):self.owner.encode(self.state([dict(actual=1)]))
        self.assertTrue(self.owner.history.store(0).path.exists())
        with self.assertRaises(NativeUIError):self.make()
        self.path.unlink()
        with self.assertRaises(NativeUIError):self.make()
    def test_reference_kind_digest_and_cross_run_scope_are_exact(self):
        encoded=self.owner.encode(dict(frames=[dict(actual=1)],replies=[dict(actual=2)],vm=dict(actual=3)))
        for key,value in (('kind','reply'),('sha256','f'*64),('snapshotOriginal',True)):
            changed=deepcopy(encoded);changed['frames'][0][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.owner.decode(changed)
        with self.assertRaises(NativeUIError):SnapshotCancelOriginals(self.path,'c'*32,BINDING)


class SnapshotPlatformTests(unittest.TestCase):
    def test_actual_sdk_selects_existing_backend_and_never_a_save_success(self):
        for sdk,backend in (('26','document-picker'),('28','document-picker'),('29','media-store'),('35','media-store')):
            value=profile(sdk);self.assertEqual(backend,value['saveBackend']);self.assertEqual('not-required',value['savePermission'])
            self.assertEqual({'snapshotAndroidPlatformVersion','sdk','saveBackend','savePermission'},set(value))
        for invalid in ('25','026',' 29','29\n','٢٩',29,True,'1001'):
            with self.subTest(invalid=invalid),self.assertRaises(NativeUIError):profile(invalid)
    def test_frozen_native_clock_cannot_hide_slow_sdk_or_last_guard_and_changed_profile(self):
        for where in ('sdk','guard'):
            clock=[1.];calls=[0]
            def guard():
                calls[0]+=1
                if where=='guard' and calls[0]==2:clock[0]+=2
            def sdk():
                if where=='sdk':clock[0]+=2
                return '29'
            owner=PicoSnapshotPlatform(sdk,guard,lambda:20000,monotonic=lambda:clock[0])
            with self.subTest(where=where),self.assertRaises(NativeUIError):owner.read()
        raw=['29'];owner=PicoSnapshotPlatform(lambda:raw[0],lambda:None,lambda:20000,monotonic=lambda:1.)
        owner.read();raw[0]='28'
        with self.assertRaises(NativeUIError):owner.read()


if __name__=='__main__':unittest.main()
