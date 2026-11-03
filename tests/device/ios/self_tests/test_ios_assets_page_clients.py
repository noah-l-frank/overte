"""Original normal client cleanup transfers page duty; never server/Model end."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_page_clients import PageLeaseUpload,PageLeaseTree,PageLeaseOriginalTree,PageLeaseUsage,PageLeaseRenamedUsage
from ios.self_tests.assets_shared_page_client_fixture import Fixture
from ios.self_tests.assets_picker_fixture import RUN,BINDING


class AssetsPageClientTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture(self);self.f.cancel_episode(1);self.scope=self.f.begin(2,format(2,'032x'))
        held=self.scope.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.picker=self.f.picker(self.scope);self.picker.open_page();self.picker.open_picker();self.picker.choose_primary()
        self.owner=self.f.upload(self.scope,self.picker);self.owner.reserve();self.root=self.owner.store.path.parent
    def uploaded(self):
        self.owner.review();self.owner.destination();self.owner.start_upload();return self.owner.uploaded()
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical read cannot query native/UI or write')
    def test_actual_upload_client_files_and_replies_retire_with_same_page_alive_and_literal_owner_refuses_v2(self):
        self.uploaded();page=deepcopy(self.f.page.identity());packet=self.owner.cleanup()
        self.assertEqual({'exists':False,'files':[]},packet['source']['files']);self.assertEqual('retired',self.owner.state['phase'])
        self.assertEqual('closed',self.owner.replies.state['phase']);self.assertEqual('page-borrowed-retired',self.picker.state['phase'])
        self.assertEqual(page,self.f.page.identity());self.assertTrue(self.f.boundary.host_state['pageAlive'])
        self.assertIn('2',self.f.page.state['transfers']);self.assertEqual(3,len(self.f.boundary.reads.data))
        self.assertFalse(any(row['slot']=='cleanup-home' for row in self.owner.state['inputs']))
        with self.assertRaises(NativeUIError):
            OwnedAssetsUpload(self.owner.native,self.owner.clock,self.owner.files,self.picker,self.owner.replies,self.owner.store,BINDING,
                lock=self.scope.locks['primary'],monotonic=self.f.boundary.monotonic,sleep=self.f.boundary.sleep)
        before={str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.iterdir() if p.is_file()}
        with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            restored=PageLeaseUpload(self.owner.native,self.owner.clock,self.owner.files,self.picker,self.owner.replies,self.owner.store,BINDING,
                lock=self.scope.locks['primary'],page_lease=self.f.page,episode=self.scope,monotonic=self.f.boundary.monotonic,sleep=self.f.boundary.sleep)
            self.assertEqual(self.owner.state,restored.state)
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.iterdir() if p.is_file()})
    def test_actual_renamed_tree_delete_and_usage_client_transfer_keep_page_and_closed_dialogs(self):
        self.uploaded();tree=PageLeaseTree(self.owner,PrivateFeatureState(self.root/'page-tree.json'),lock=self.scope.locks['primary'])
        tree.reserve();tree.browse();tree.rename();usage=PageLeaseRenamedUsage(self.owner,PrivateFeatureState(self.root/'page-usage.json'),
            lock=self.scope.locks['primary'],tree=tree);usage.reserve();usage.select();tree.delete();usage.close_clients();tree.close_clients()
        self.assertIsNotNone(tree.state['clientClosedBy']);self.assertIsNotNone(usage.state['clientClosedBy'])
        self.assertEqual({},self.f.boundary.reads.data);self.assertTrue(self.f.boundary.host_state['pageAlive'])
        self.assertFalse(self.f.boundary.host_state['treeInfo']['renameVisible']);self.assertFalse(self.f.boundary.host_state['treeInfo']['deleteVisible'])
        self.assertEqual(3,tree.previous['iosAssetsTreeOwnerVersion']);self.assertEqual(4,usage.previous['iosAssetsUsageOwnerVersion'])
    def complete_gltf_client(self):
        self.uploaded();tree=PageLeaseTree(self.owner,PrivateFeatureState(self.root/'transition-tree.json'),lock=self.scope.locks['primary'])
        tree.reserve();tree.browse();tree.rename();tree.delete();tree.close_clients()
        self.assertEqual({},self.f.boundary.reads.data)
    def staged_upload(self,index):
        scope=self.f.begin(index,format(index,'032x'));held=scope.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        picker=self.f.picker(scope);picker.open_page();picker.open_picker();picker.choose_primary();owner=self.f.upload(scope,picker)
        owner.reserve();owner.review();owner.destination();owner.start_upload();owner.uploaded();return scope,owner
    def test_OBJ_original_tree_deletes_without_rename_and_transfers_actual_client_quiet_on_same_page(self):
        self.complete_gltf_client();scope,owner=self.staged_upload(3);root=owner.store.path.parent
        tree=PageLeaseOriginalTree(owner,PrivateFeatureState(root/'obj-page-tree.json'),lock=scope.locks['primary'])
        tree.reserve();tree.browse();tree.delete();tree.close_clients()
        self.assertEqual(4,tree.previous['iosAssetsTreeOwnerVersion']);self.assertFalse(any('rename' in row['slot'] for row in tree.state['inputs']))
        self.assertEqual({},self.f.boundary.reads.data);self.assertIn('3',self.f.page.state['transfers']);self.assertTrue(self.f.boundary.host_state['pageAlive'])
    def test_FBX_usage_dialog_cancel_and_transfer_do_not_infer_model_or_server_retirement(self):
        self.complete_gltf_client();self.f.cancel_episode(3);scope,owner=self.staged_upload(4);root=owner.store.path.parent
        usage=PageLeaseUsage(owner,PrivateFeatureState(root/'fbx-page-usage.json'),lock=scope.locks['primary'])
        usage.reserve();usage.select();usage.open_model();usage.cancel_model();usage.close_clients()
        self.assertEqual(3,usage.previous['iosAssetsUsageOwnerVersion']);self.assertIsNotNone(usage.state['clientClosedBy'])
        self.assertFalse(self.f.boundary.host_state['usageInfo']['model']['visible']);self.assertIn('4',self.f.page.state['transfers'])
        self.assertTrue(self.f.boundary.host_state['pageAlive']);self.assertEqual(1,len(self.f.boundary.reads.data))
        self.assertFalse(any(row['id']=='assets.model.accept' for row in usage.state['inputs']))
    def test_unresolved_ignored_input_ack_cannot_be_abandoned_on_live_shared_page(self):
        self.f.boundary.configure(ignore='asset-file.select')
        with self.assertRaises(NativeUIError):self.owner.review()
        before=len(self.f.boundary.inputs)
        with self.assertRaises(NativeUIError):self.owner.cleanup(abort=True)
        self.assertEqual(before,len(self.f.boundary.inputs));self.assertEqual('staged',self.owner.files.state['phase'])
        self.assertNotIn('2',self.f.page.state['transfers']);self.assertTrue(self.f.boundary.host_state['pageAlive'])
    def test_actual_live_upload_consumer_blocks_file_release_and_parent_transfer(self):
        self.uploaded();self.f.boundary.hold_consumer()
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual('staged',self.owner.files.state['phase']);self.assertNotIn('2',self.f.page.state['transfers'])
        self.assertTrue(self.f.boundary.host_state['pageAlive']);self.assertNotEqual('retired',self.owner.state['phase'])


if __name__=='__main__':unittest.main()
