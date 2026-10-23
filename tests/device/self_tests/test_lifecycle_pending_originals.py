"""Actual private original files and immutable inspection boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_pending_originals import LifecyclePendingOriginals
from self_tests.test_pico_lifecycle_world import BINDING,RUN


class LifecyclePendingOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-pending-originals-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.path=self.root/'lifecycle-pending-originals.json'
        self.owner=LifecyclePendingOriginals(self.path,RUN,BINDING)
        self.original={'source':frame('{"actual":1}\n')};self.reference=self.owner.encode(self.original)

    def test_complete_original_bytes_survive_cold_load_and_inspection_copy_changes(self):
        rows=self.owner.frames;rows[0]['raw']='changed inspection copy'
        self.assertEqual(self.original,self.owner.decode(self.reference))
        cold=LifecyclePendingOriginals(self.path,RUN,BINDING)
        self.assertEqual(self.original,cold.decode(self.reference));self.assertEqual(self.owner.root_stamp,cold.root_stamp)

    def test_replaced_memory_tuple_or_mutated_index_cannot_be_adopted(self):
        original=self.owner.memory.raws;self.owner.memory.raws=tuple([b'{}'])
        with self.assertRaises(NativeUIError):self.owner.decode(self.reference)
        self.owner.memory.raws=original;self.owner.by_hash[next(iter(self.owner.by_hash))]=True
        with self.assertRaises(NativeUIError):self.owner.decode(self.reference)

    def test_same_bytes_root_or_child_replacement_refuses_original_identity(self):
        for path in (self.path,self.owner.history.store(0).path):
            if path==self.path:owner=self.owner
            else:owner=LifecyclePendingOriginals(self.path,RUN,BINDING)
            raw=path.read_bytes();replacement=path.with_name(path.name+'.replacement')
            replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            with self.assertRaises(NativeUIError):owner.decode(self.reference)

    def test_foreign_scope_and_orphan_child_cannot_create_a_cold_owner(self):
        with self.assertRaises(NativeUIError):LifecyclePendingOriginals(self.path,'b'*32,BINDING)
        orphan=self.owner.history.store(1).path;orphan.write_text('{}\n');orphan.chmod(0o600)
        with self.assertRaises(NativeUIError):LifecyclePendingOriginals(self.path,RUN,BINDING)


if __name__=='__main__':unittest.main()
