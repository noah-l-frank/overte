"""Actual orphan files and missing-parent guard; no End/OS/SDK authority.

These focused cases exercise the filesystem gate called before End Context
construction. They do not substitute a Graph, journey, SDK or native proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.snapshot_photos_end_owner import initial_process_inventory
from ios.adapters.process_retirement import filename
from ios.self_tests.retained_host_roots import retain_owned_root


class PhotosEndOrphanFilesTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='photos-end-orphan-root-')
        self.root=Path(self.temporary.name);self.root.chmod(0o700)
        retain_owned_root(self.temporary,expected_root=self.root)
        self.addCleanup(self.temporary.cleanup)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.parent=PrivateFeatureState(self.root/'photos-sdk-end-owner.json')
        self.process=self.root/filename('snapshotphotos','primary',0)

    def pin(self,path):
        info=path.lstat()
        return tuple(getattr(info,key) for key in ('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink',
            'st_size','st_mtime_ns','st_ctime_ns'))+(path.read_bytes(),)

    def forbidden(self,*_args,**_kwargs):
        raise AssertionError('Orphan admission must not write, discard or manufacture an original')

    def test_fresh_scope_with_existing_graph_and_other_owners_remains_read_only(self):
        graph=PrivateFeatureState(self.root/'photos-sdk-end-graph.json')
        graph.write({'declaredMetadataOnly':'graph file is not a native or End proof'},None)
        other=PrivateFeatureState(self.root/'ios-snapshot-primary-owner.json')
        other.write({'declaredMetadataOnly':'another owner stays outside this process namespace'},None)
        pins={path:self.pin(path) for path in (graph.path,other.path)}
        with self.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden),patch.object(PrivateFeatureState,'discard',side_effect=self.forbidden):
            initial_process_inventory(self.root,self.lock)
        self.assertIsNone(self.parent.read());self.assertEqual(pins,{path:self.pin(path) for path in pins})

    def test_lost_parent_wal_cannot_adopt_existing_process_wal_or_create_a_fresh_end_owner(self):
        external=tempfile.TemporaryDirectory(prefix='photos-end-parent-original-')
        retained=Path(external.name);retain_owned_root(external,expected_root=retained);self.addCleanup(external.cleanup)
        self.assertNotEqual(retained,self.root)
        self.parent.write({'declaredMetadataOnly':'retained previous parent intent, no native fact'},None)
        process=PrivateFeatureState(self.process)
        process.write({'declaredMetadataOnly':'existing process responsibility must block regardless of body'},None)
        old_parent=retained/'photos-sdk-end-owner.original.json';self.parent.path.rename(old_parent)
        pins={path:self.pin(path) for path in (old_parent,self.process)}
        with self.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden),patch.object(PrivateFeatureState,'discard',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):initial_process_inventory(self.root,self.lock)
        self.assertIsNone(self.parent.read());self.assertEqual(pins,{path:self.pin(path) for path in pins})

    def test_record_only_orphan_is_not_hidden_by_a_missing_process_wal(self):
        record=self.process.with_name(self.process.stem+'-1.json')
        record.write_bytes(b'Opened original record prefix; deliberately no native authority');record.chmod(0o600)
        before=self.pin(record);self.assertFalse(self.process.exists())
        with self.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):initial_process_inventory(self.root,self.lock)
        self.assertEqual(before,self.pin(record));self.assertIsNone(self.parent.read())

    def test_same_bytes_on_another_orphan_inode_cannot_reanchor_the_missing_parent(self):
        external=tempfile.TemporaryDirectory(prefix='photos-end-process-original-')
        retained=Path(external.name);retain_owned_root(external,expected_root=retained);self.addCleanup(external.cleanup)
        self.process.write_bytes(b'Actual same-byte local orphan metadata, not a product fact');self.process.chmod(0o600)
        old=retained/'process-owner.original.json';raw=self.process.read_bytes();self.process.rename(old)
        self.process.write_bytes(raw);self.process.chmod(0o600)
        self.assertNotEqual(old.stat().st_ino,self.process.stat().st_ino)
        pins={path:self.pin(path) for path in (old,self.process)}
        with self.lock.held(),patch.object(PrivateFeatureState,'discard',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):initial_process_inventory(self.root,self.lock)
        self.assertEqual(pins,{path:self.pin(path) for path in pins});self.assertIsNone(self.parent.read())


if __name__=='__main__':unittest.main()
