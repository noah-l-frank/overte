"""Actual bound cleanup refuses warm/rootless operation ownership before IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import test_normal_create as canonical
from adapters.pico4.create_operation_owner import owner_path
from adapters.normal_feature_state import PrivateFeatureState
from test_create_journey import RUN,URL


class CreateOperationBindingTests(unittest.TestCase):
    def setUp(self):
        self.h=canonical.PicoCreateTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adapter,self.native=self.h.instance,self.h.native
        self.path=owner_path(self.adapter,self.native.target,RUN)
    def originals(self):
        rows={}
        for path in self.path.parent.rglob('*'):
            if path.is_file():
                info=path.lstat();rows[str(path)]=(hashlib.sha256(path.read_bytes()).hexdigest(),info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        return rows
    def refused_before_io(self):
        before=self.originals();inputs=list(self.native.inputs)
        with ExitStack() as patches:
            methods=[]
            for name in dir(self.native):
                if not name.startswith('_') and callable(getattr(self.native,name)):
                    methods.append(patches.enter_context(patch.object(self.native,name,side_effect=AssertionError('Unexpected native read/write'))))
            base=patches.enter_context(patch.object(type(self.adapter).__mro__[1],'cleanup',side_effect=AssertionError('Unexpected base stop')))
            with self.assertRaisesRegex(ValueError,'OVT_PICO_BINDING_REJECTED'):self.adapter.cleanup(self.native.target)
            self.assertTrue(all(method.call_count==0 for method in methods));base.assert_not_called()
        self.assertEqual(inputs,self.native.inputs);self.assertEqual(before,self.originals())
    def test_actual_canonical_factory_owner_blocks_generic_cleanup_before_native_or_base_stop(self):
        config=self.path.with_name('read-only-create-fixture-config.json')
        PrivateFeatureState(config).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL.split('/runs/')[0],adapterToken='private-adapter-'+'a'*40),None)
        with patch.dict(os.environ,{'OVERTE_PICO_FEATURE_FIXTURE_CONFIG':str(config)}):
            owner=self.adapter._create_operation_owner(self.native.target,RUN,URL)
            self.assertEqual(self.path,owner.path);self.assertEqual(0,owner.factory_calls);self.assertIsNone(owner.parent)
            self.refused_before_io()
    def test_actual_rootless_peer_config_and_unknown_pending_block_without_namespace_changes(self):
        for index,suffix in enumerate(('.peer-config.json','.json.pending-unknown')):
            if index:self.setUp()
            with self.subTest(suffix=suffix):
                orphan=self.path.with_name(self.path.stem+suffix);orphan.write_bytes(b'original retained unknown bytes\n');orphan.chmod(0o600)
                self.assertFalse(self.path.exists());self.refused_before_io()
                # Each independent fixture namespace and its original inode
                # remain retained, including this refused orphan.


if __name__=='__main__':unittest.main()
