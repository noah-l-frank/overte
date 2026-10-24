"""Actual local Scope/key/pointer files; no complete paired end authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rooted_fence_original import local
from ios.self_tests import test_ios_emote_rooted_fence as fixture


class RootedFenceOriginalTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.RootedFenceLocalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.scope=self.f.scope
        self.copies={str(owner.store.path):owner.store.read() for owner in (self.scope,self.f.f.keys,self.f.f.pointers)}
        self.value=self.f.local();self.value.update(archiveSha256='a'*64,sealSha256='b'*64)
    def decoded(self,value=None):
        return local(self.value if value is None else value,self.copies,root=self.scope.root,binding=self.scope.binding,
            run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
    def test_exact_real_appends_reopen_without_any_native_getter_or_changed_frozen_copy(self):
        frozen=deepcopy(self.copies);actions=list(self.f.domain.io.actions);sequences=dict(self.f.domain.sequences)
        result=self.decoded();self.assertEqual(self.scope.held_originals(),result['scope'].held_originals())
        self.assertEqual(3,len(result['metadata']));self.assertEqual(frozen,self.copies)
        self.assertEqual(actions,self.f.domain.io.actions);self.assertEqual(sequences,self.f.domain.sequences)
    def test_fictional_acquisition_native_clock_or_hold_cannot_replace_actual_original(self):
        for field in ('acquisitions','nativeClock','held'):
            changed=deepcopy(self.value)
            if field=='acquisitions':changed[field][0]['hostBeforeEpochMs']-=1
            elif field=='nativeClock':changed[field]['after']['monotonicMs']+=1
            else:changed[field]=[]
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.decoded(changed)
    def test_foreign_or_missing_current_local_wal_is_not_reconstructed_from_frozen_metadata(self):
        changed=deepcopy(self.value);changed['keys']=deepcopy(self.copies[str(self.f.f.keys.store.path)])
        with self.assertRaises(NativeUIError):self.decoded(changed)
        self.f.f.pointers.store.path.unlink()
        with self.assertRaises(NativeUIError):self.decoded()
    def test_missing_actual_native_original_blocks_pure_replay(self):
        keys=self.f.f.keys;row=keys.original(keys.state['records'][-1]);path=keys.raw.originals.path(keys.raw.original(row['wire']))
        path.unlink()
        with self.assertRaises((NativeUIError,OSError)):self.decoded()


if __name__=='__main__':unittest.main()
