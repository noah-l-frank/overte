"""Private full-history scaling and durable failure boundaries, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import random
import os
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.source_chunks import ChatSourceChunks, digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack, unpack
from self_tests import test_chat_journey_samples as seams


class SourceChunkTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def read(self,index):return self.h.samples.read(f'{index:032x}',20000)
    def queries(self):return [len(source.commands) for source in (self.h.primary,self.h.peer,self.h.view,self.h.native)]
    def test_355_distinct_complete_256_joint_sources_survive_original_flat_limit_and_reconstruct_without_queries(self):
        rng=random.Random(8319)
        self.h.native.mutate=lambda value:value['animation'].update(joints=[[0.0,0.0,0.0,1.0,*[rng.uniform(-1,1) for _ in range(3)]] for _ in range(256)])
        for index in range(355):self.read(index)
        self.assertEqual(355,len(self.h.samples.frames));self.assertEqual(355,len(self.h.store.read()['chunks']))
        self.assertTrue(all(path.stat().st_size<=65536 and path.stat().st_mode&0o777==0o600 for path in self.h.root.iterdir() if '.frame-' in path.name))
        self.assertLess(self.h.store.path.stat().st_size,65536)
        with self.assertRaises(NativeUIError):pack(self.h.samples.frames)
        originals=deepcopy(self.h.samples.frames);before=self.queries();rebuilt=self.h.sampler()
        self.assertEqual(before,self.queries());self.assertEqual(originals,rebuilt.frames)
        self.assertEqual(355,len({frame['lifecycle']['requestId'] for frame in rebuilt.frames}))
        self.h.samples=rebuilt;self.read(356)
        self.assertEqual([count+1 for count in before],self.queries())
        self.assertEqual(originals,rebuilt.frames[:-1])
    def test_missing_altered_permission_or_foreign_chunk_refuses_before_dispatch(self):
        for fault in ('missing','altered','permissions','foreign','reordered','hardlink','symlink'):
            with self.subTest(fault=fault):
                self.setUp();self.read(1);self.read(2);before=self.queries();root=self.h.store.read()
                child=self.h.samples.history.store(0);old=child.read()
                if fault=='missing':child.path.unlink()
                elif fault=='permissions':child.path.chmod(0o644)
                elif fault=='altered':child.write(old|dict(index=1),old)
                elif fault=='hardlink':os.link(child.path,self.h.root/'hard')
                elif fault=='symlink':
                    child.path.unlink();child.path.symlink_to(self.h.root/'missing')
                elif fault=='foreign':
                    changed=old|dict(scopeSha256='f'*64);child.write(changed,old)
                    root2=root|dict(chunks=[digest(changed),root['chunks'][1]]);self.h.store.write(root2,root)
                else:self.h.store.write(root|dict(chunks=list(reversed(root['chunks']))),root)
                with self.assertRaises(NativeUIError):self.h.sampler()
                self.assertEqual(before,self.queries())
    def test_deleted_root_does_not_adopt_or_overwrite_orphan_originals(self):
        self.read(1);child=self.h.samples.history.store(0);original=child.path.read_bytes();self.h.store.path.unlink();before=self.queries()
        with self.assertRaises(NativeUIError):self.h.sampler()
        self.assertEqual(original,child.path.read_bytes());self.assertEqual(before,self.queries())
    def test_existing_chunk_tampering_is_detected_by_live_owner_before_new_queries(self):
        self.read(1);before=self.queries();child=self.h.samples.history.store(0);old=child.read();child.write(old,old)
        with self.assertRaises(NativeUIError):self.read(2)
        self.assertEqual(before,self.queries());self.assertEqual('ready',self.h.store.read()['phase'])
    def test_lost_child_write_retains_reading_intent_and_never_requeries_or_adopts(self):
        original=PrivateFeatureState.write
        def lost(store,value,previous):
            original(store,value,previous)
            if '.frame-' in store.path.name:raise NativeUIError('lost after original child write')
        with patch.object(PrivateFeatureState,'write',lost):
            with self.assertRaises(NativeUIError):self.read(1)
        before=self.queries();self.assertEqual('reading',self.h.store.read()['phase'])
        self.assertTrue(self.h.samples.history.store(0).path.exists())
        with self.assertRaises(NativeUIError):self.h.sampler()
        with self.assertRaises(NativeUIError):self.read(2)
        self.assertEqual(before,self.queries())
    def test_failed_root_commit_keeps_every_original_file_and_unresolved_reading(self):
        self.read(1);first=self.h.samples.history.store(0).path.read_bytes();original=self.h.store.write
        def failed(value,previous):
            if value['phase']=='ready':raise NativeUIError('root commit unavailable')
            original(value,previous)
        self.h.store.write=failed
        with self.assertRaises(NativeUIError):self.read(2)
        self.assertEqual('reading',self.h.store.read()['phase'])
        self.assertEqual(first,self.h.samples.history.store(0).path.read_bytes())
        self.assertTrue(self.h.samples.history.store(1).path.exists())
        with self.assertRaises(NativeUIError):self.h.sampler()
    def test_final_native_guard_cannot_change_an_original_child_after_its_last_check(self):
        self.read(1);changed=False;guard=self.h.samples.primary.guard
        def mutate():
            nonlocal changed
            if len(self.h.samples.frames)==2 and not changed:
                child=self.h.samples.history.store(0);value=child.read();child.write(value,value);changed=True
            return guard()
        self.h.samples.primary.guard=mutate
        with self.assertRaises(NativeUIError):self.read(2)
        self.assertTrue(changed);self.assertEqual('ready',self.h.store.read()['phase']);self.assertEqual(2,len(self.h.samples.frames))

    def test_frozen_host_late_final_chunk_commit_cannot_refresh_old_original_clocks(self):
        delta=0;original=ChatSourceChunks.append
        def late(owner,*args):
            nonlocal delta
            result=original(owner,*args);delta=2000;return result
        self.h.samples.primary.clock_ms=lambda:20000+delta
        with patch.object(ChatSourceChunks,'append',late):
            with self.assertRaises(NativeUIError):self.read(1)
        self.assertEqual('ready',self.h.store.read()['phase']);self.assertEqual(1,len(self.h.samples.frames));self.assertEqual(0,self.h.clock)
    def test_global_original_raw_bound_still_fails_closed_without_erasing_prior_chunks(self):
        self.read(1);first=self.h.samples.history.store(0).path.read_bytes()
        with patch('adapters.chat_journey.source_chunks.MAX_RAW',2):
            with self.assertRaises(NativeUIError):self.read(2)
        self.assertEqual('reading',self.h.store.read()['phase'])
        self.assertEqual(first,self.h.samples.history.store(0).path.read_bytes())
        self.assertFalse(self.h.samples.history.store(1).path.exists())

    def test_old_flat_v3_is_retained_without_migration_or_live_queries(self):
        root=self.h.samples.base;old={key:value for key,value in root.items() if key!='chunks'}|dict(chatSamplesVersion=3,transcript=pack([]))
        self.h.store.write(old,None);before=self.queries()
        with self.assertRaises(NativeUIError):self.h.sampler()
        self.assertEqual(old,self.h.store.read());self.assertEqual(before,self.queries())

    def test_complete_inventory_and_root_namespace_still_refuse_foreign_files(self):
        self.read(1);history=self.h.samples.history
        extra=history.root.path.with_name(history.prefix+'foreign.json');extra.write_text('{}');extra.chmod(0o600)
        with self.assertRaises(NativeUIError):history.verify()
        extra.unlink();history.verify();original=history.root.path
        history.root.path=original.with_name('different-root.json')
        with self.assertRaises(NativeUIError):history.inventory(1)
        with self.assertRaises(NativeUIError):history.store(0)
        history.root.path=original;history.verify()


if __name__=='__main__':unittest.main()
