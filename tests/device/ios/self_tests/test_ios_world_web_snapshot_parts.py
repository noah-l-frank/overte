"""Actual inode-bound single parent; projection proof never accepts wanted DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_snapshot_parts import WorldWebSnapshotParts
from ios.self_tests.world_web_snapshot_fixture import SnapshotNative
from ios.self_tests.world_web_sources_fixture import RUN,URL
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebSnapshotPartsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700);self.intents=[]
        self.owner=SimpleNamespace(store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json'),binding=BINDING,run=RUN,role='primary',pid=42,
            phase=SimpleNamespace(fixture_url=URL),guard=lambda:True,monotonic=lambda:1.,snapshot_storage_intent=lambda *args:self.intents.append(deepcopy(args)),
            state=dict(pending=dict(start=dict(nativeBefore=dict(requestId='ios-'+'e'*32)))))
        self.parts=WorldWebSnapshotParts(self.owner);self.batch=SnapshotNative(document=True)
        from ios.adapters.world_web_snapshot import ACTION
        self.query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=ACTION,runId=RUN,fixtureUrl=URL);self.batch.send(self.query)
    def test_one_actual_parent_preserves_all_original_modules_and_no_duplicate_original_files(self):
        parent=self.parts.write(1,self.batch.last);initial=set(self.root.iterdir());projected=self.parts.project(parent)
        from ios.adapters.world_web_snapshot import body
        expected=body(self.batch.last)[1]
        with self.parts.validation_round():
            self.assertEqual(expected,{name:self.parts.read(reference) for name,reference in projected.items()})
        self.assertEqual(initial,set(self.root.iterdir()));self.assertEqual(['planned','opened','saved'],[row[1]['phase'] for row in self.intents])
        projected['world']['ordinal']=1
        with self.assertRaises(NativeUIError):self.parts.read(projected['world'])
    def test_warm_pure_parent_is_reopened_once_in_each_fresh_actual_file_read_membership_scope(self):
        from adapters.original_file_reads import scope
        parent=self.parts.write(1,self.batch.last);refs=self.parts.project(parent);read=self.parts.read_bytes
        with patch.object(self.parts,'read_bytes',wraps=read) as actual:
            with self.parts.validation_round():
                self.parts.read(refs['world']);self.assertEqual(1,actual.call_count)
                for expected in (2,3):
                    with scope(fresh=True) as reads:
                        self.parts.read(refs['world']);self.parts.read(refs['keys'])
                        self.assertTrue(set(self.parts.paths(parent))<=reads);self.assertEqual(expected,actual.call_count)
    def test_actual_bytes_are_read_before_reuse_every_use_and_exit_keep_exact_private_file_identity(self):
        parent=self.parts.write(1,self.batch.last);projected=self.parts.project(parent)
        read=self.parts.read_bytes
        with patch.object(self.parts,'read_bytes',wraps=read) as actual:
            with self.parts.validation_round():
                for reference in projected.values():self.parts.read(reference)
            self.assertEqual(1,actual.call_count)
            with self.parts.validation_round():self.parts.read(projected['world'])
            self.assertEqual(2,actual.call_count)
        for index,fault in enumerate(('bytes','inode','delete','mode','link'),2):
            parent=self.parts.write(index,self.batch.last);projected=self.parts.project(parent)
            path=self.parts.paths(parent)[0];raw=path.read_bytes()
            with self.subTest(fault=fault):
                try:
                    with self.assertRaises((NativeUIError,FileNotFoundError)):
                        with self.parts.validation_round():
                            self.parts.read(projected['world'])
                            if fault=='bytes':path.write_bytes(raw.replace(b'offset',b'Offset',1))
                            elif fault=='inode':path.unlink();path.write_bytes(raw);path.chmod(0o600)
                            elif fault=='delete':path.unlink()
                            elif fault=='mode':path.chmod(0o644)
                            else:__import__('os').link(path,path.with_suffix('.link'))
                            self.parts.read(projected['keys'])
                finally:
                    link=path.with_suffix('.link')
                    if link.exists():link.unlink()
                    if path.exists():path.unlink()
                    path.write_bytes(raw);path.chmod(0o600)
    def test_outward_mutation_and_warm_header_relabel_cannot_poison_actual_parent(self):
        parent=self.parts.write(1,self.batch.last);refs=self.parts.project(parent)
        with self.parts.validation_round():
            value=self.parts.read(refs['world']);value['processId']=999
            self.assertEqual(42,self.parts.read(refs['world'])['processId'])
            original,parts=self.parts.original(parent);original['instance']='0'*32;parts['keys']['source']['instance']='0'*32
            self.assertNotEqual('0'*32,self.parts.original(parent)[0]['instance'])
            self.owner.pid=43
            with self.assertRaises(NativeUIError):self.parts.read(refs['world'])
        self.owner.pid=42
    def test_wanted_projection_name_parent_hash_acquisition_or_ordinal_cannot_replace_actual_original(self):
        parent=self.parts.write(1,self.batch.last);refs=self.parts.project(parent)
        for fault in ('name','parent','acquisition','ordinal','bool'):
            ref=deepcopy(refs['world'])
            if fault=='name':ref['name']='widgets'
            elif fault=='parent':ref['parent']['sha256']='0'*64
            elif fault=='acquisition':ref['acquisitionId']='ios-'+'a'*32
            elif fault=='bool':ref['ordinal']=True
            else:ref['ordinal']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.parts.read(ref)

    def test_verification_only_path_keeps_actual_bytes_scope_identity_and_exact_selected_original(self):
        parent=self.parts.write(1,self.batch.last);refs=self.parts.project(parent);read=self.parts.read_bytes
        with patch.object(self.parts,'read_bytes',wraps=read) as actual:
            with self.parts.validation_round():
                for reference in refs.values():self.assertIsNone(self.parts.verify_projection(reference))
                forged=deepcopy(refs['world']);forged['ordinal']=1
                with self.assertRaises(NativeUIError):self.parts.verify_projection(forged)
                self.assertEqual(1,actual.call_count)
            self.parts.verify_projection(refs['world']);self.assertEqual(2,actual.call_count)
        path=self.parts.paths(parent)[0];raw=path.read_bytes()
        with self.assertRaises(NativeUIError):
            with self.parts.validation_round():
                self.parts.verify_projection(refs['world'])
                replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                self.parts.verify_projection(refs['keys'])


if __name__=='__main__':unittest.main()
