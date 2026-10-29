"""Passive metadata/IO barriers only; these do not qualify a typed End graph."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack,contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import collect,readonly,scope as membership
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import snapshot_photos_end_read_area as source


class PassiveMutationBarrierTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.store=PrivateFeatureState(self.root/'owned.json')
        self.value={'original':1};self.store.write(self.value,None)
    def test_default_writer_and_discard_remain_available(self):
        self.store.write({'original':2},self.value);self.store.discard({'original':2});self.assertIsNone(self.store.read())
    def test_write_and_discard_fail_before_any_mutation(self):
        before=(self.store.path.stat(),self.store.path.read_bytes())
        with readonly():
            with self.assertRaises(NativeUIError):self.store.write({'original':2},self.value)
            with self.assertRaises(NativeUIError):self.store.discard(self.value)
        after=(self.store.path.stat(),self.store.path.read_bytes())
        self.assertEqual((before[0].st_ino,before[0].st_mtime_ns,before[0].st_ctime_ns,before[1]),
            (after[0].st_ino,after[0].st_mtime_ns,after[0].st_ctime_ns,after[1]))
    def test_nested_exception_preserves_outer_barrier_then_resets(self):
        with readonly():
            with self.assertRaisesRegex(RuntimeError,'sentinel'):
                with readonly():raise RuntimeError('sentinel')
            with self.assertRaises(NativeUIError):self.store.discard(self.value)
        self.store.discard(self.value);self.assertIsNone(self.store.read())
    def test_barrier_precedes_even_parent_path_validation(self):
        store=PrivateFeatureState(Path('not-an-admitted-parent')/'owned.json')
        with readonly():
            with self.assertRaisesRegex(NativeUIError,'prohibits private state mutation'):store.write({},None)
            with self.assertRaisesRegex(NativeUIError,'prohibits private state mutation'):store.discard(None)


class PassiveReadAreaMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.parent=Path(temporary.name);self.parent.chmod(0o700)
        self.roots={name:self.parent/name for name in ('main','photos','archive')};self.locks={}
        for name,root in self.roots.items():root.mkdir(mode=0o700);self.locks[name]=ScriptSourceLock(root/'script-feature-sources.lock')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)
        self.bindings={name:dict(self.binding) for name in self.roots};self.run='a'*32
        self.url='https://controlled.invalid/feature-fixture/v1/runs/'+self.run+'/'
        self.path=self.roots['main']/'metadata-only.json';PrivateFeatureState(self.path).write({'metadataOnly':True},None)
    @contextmanager
    def area(self):
        with ExitStack() as stack:
            for lock in self.locks.values():stack.enter_context(lock.held())
            with source.scope(self.roots,self.locks,self.bindings,self.run,self.url) as area:yield area
    def test_actual_raw_reread_enters_independent_nested_membership(self):
        with self.area() as area:
            with collect() as outer:
                with membership(fresh=True) as inner:area.reread({self.path})
            self.assertEqual({self.path},outer);self.assertEqual({self.path},inner)
    def test_nested_area_is_rejected_and_exception_clears_context(self):
        with self.assertRaisesRegex(RuntimeError,'sentinel'):
            with self.area():
                with self.assertRaises(NativeUIError):
                    with source.scope(self.roots,self.locks,self.bindings,self.run,self.url):pass
                raise RuntimeError('sentinel')
        self.assertIsNone(source._ACTIVE.get())
        PrivateFeatureState(self.path).write({'metadataOnly':False},{'metadataOnly':True})
    def test_identical_bytes_new_inode_is_rejected(self):
        with self.assertRaises(NativeUIError):
            with self.area() as area:
                replacement=self.path.with_name('replacement.json');replacement.write_bytes(self.path.read_bytes());replacement.chmod(0o600);replacement.replace(self.path)
                area.reread({self.path})
    def test_extra_original_file_is_rejected(self):
        with self.assertRaises(NativeUIError):
            with self.area() as area:
                self.path.with_name('unexpected.json').write_bytes(b'{}');area.check()
    def test_scope_binding_and_parser_changes_are_rejected(self):
        with self.assertRaises(NativeUIError):
            with self.area() as area:area.bindings['main']['generation']=1;area.check()
        with self.assertRaises(NativeUIError):
            with self.area() as area:
                with patch.object(area.parser_module,'data',lambda *_a,**_k:None):area.check()
    def test_unread_foreign_path_cannot_be_added_as_membership(self):
        with self.area() as area:
            with collect() as reads:
                with self.assertRaises(NativeUIError):area.reread({self.parent/'foreign.json'})
            self.assertEqual(set(),reads)


if __name__=='__main__':unittest.main()
