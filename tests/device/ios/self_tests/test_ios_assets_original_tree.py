"""Actual original QML Delete without an extra rename and once-only recovery.

Server/Qt/native boundaries remain models. Original normal inputs, independent
actual backend files/read replies, ownership decoders and WALs execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_original_tree import OwnedAssetsOriginalTree
from ios.self_tests.assets_unbaked_fixture import Fixture,RUN


class AssetsOriginalTreeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close)
        self.runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.fixture.boundary.monotonic)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.fixture))
        f=self.fixture;f.boundary.reads.resource='obj-bundle/main.obj';parts=f.parts()
        self.parts=self.runtime._assets_prepare_unbaked_upload('existing-component-parts',RUN,'primary',f.files.url,'b'*32,
            f.lock,f.backend.config,resource='obj-bundle/main.obj',parts=parts)
        self.tree=OwnedAssetsOriginalTree(parts['upload'],parts['tree'].store,lock=f.lock)
        self.tree.reserve();self.tree.browse()
    def mapping_changes(self):
        return [change for event in self.fixture.boundary.host_state['bundleInfo']['serviceEvents']
            if event['kind']=='mapping-completed' for change in event['changes']]
    def test_normal_original_folder_delete_never_renames_and_independent_original_mappings_disappear(self):
        tree=self.tree;before=deepcopy(self.fixture.backend.mappings);prefix='/e2e-'+RUN+'/'
        tree.delete();self.assertEqual('deleted',tree.state['phase'])
        self.assertEqual({path:value for path,value in before.items() if not path.startswith(prefix)},self.fixture.backend.mappings)
        self.assertTrue(self.mapping_changes());self.assertTrue(all(row['to'] is None for row in self.mapping_changes()))
        self.assertFalse(any(row['id'].startswith('assets.rename') for row in tree.state['inputs']))
        self.assertEqual(2,tree.previous['iosAssetsTreeOwnerVersion']);tree.close_clients()
        self.assertEqual('retired',tree.upload.state['phase']);self.assertIsNotNone(tree.state['clientClosedBy'])
    def test_lost_actual_delete_return_cold_owner_observes_original_absence_without_second_input(self):
        f=self.fixture;f.boundary.configure(lost='assets.delete.accept')
        with self.assertRaises(NativeUIError):self.tree.delete()
        self.assertEqual('deleting',self.tree.state['phase']);inputs=deepcopy(f.boundary.inputs)
        reopened=OwnedAssetsOriginalTree(f.owner(),self.tree.store,lock=f.lock)
        reopened.finish_delete();self.assertEqual('deleted',reopened.state['phase']);self.assertEqual(inputs,f.boundary.inputs)
        self.assertTrue(all(row['to'] is None for row in self.mapping_changes()))
        reopened.close_clients();self.assertIsNotNone(reopened.state['clientClosedBy'])
    def test_ignored_delete_ack_keeps_actual_mapping_and_deletion_responsibility(self):
        f=self.fixture;f.boundary.configure(ignore='assets.delete.accept');before=deepcopy(f.backend.mappings)
        with self.assertRaises(NativeUIError):self.tree.delete()
        self.assertEqual(before,f.backend.mappings);self.assertEqual('deleting',self.tree.state['phase'])
        self.assertIsNone(self.tree.state['inputs'][-1]['resolvedBy'])
        self.assertEqual([],self.mapping_changes())
