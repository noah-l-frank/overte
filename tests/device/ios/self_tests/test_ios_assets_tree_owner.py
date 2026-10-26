"""Durable ordinary mapping actions after actual original-QML bundle upload.

Native/Qt/server boundaries are declared models; real files, original QML JS,
immutable clock/UI originals, weak holders and binary reply codecs execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_session_owners import inspect_directory
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests.assets_tree_fixture import Fixture,RUN


class AssetsTreeOwnerTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.path=Path(directory.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary
        for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies'),('tree_store','tree')):
            getattr(self.f,attribute).path=self.path/('ios-assets-'+RUN+'-primary-'+kind+'.json')
        self.foreign='/foreign/keep.txt';raw=b'Actual independent foreign server input'
        self.b.reads.data[self.foreign]=raw;self.b.configure(serverRows=[dict(path=self.foreign,base64=base64.b64encode(raw).decode())])

    def start(self):
        self.upload=self.f.uploaded();self.owner=self.f.tree_owner(self.upload);self.owner.reserve();return self.owner

    def test_original_upload_browse_rename_delete_and_client_retirement_preserve_unowned_mappings(self):
        owner=self.start();owner.browse();owner.rename();last=owner.delete()
        self.assertEqual([self.foreign],[row['path'] for row in last['mappings']]);self.assertEqual('deleted',owner.state['phase'])
        before=len(self.b.inputs);restored=self.f.tree_owner(self.f.owner());self.assertEqual('deleted',restored.state['phase']);self.assertEqual(before,len(self.b.inputs))
        restored.close_clients();self.assertIsNotNone(restored.state['clientClosedBy']);self.assertEqual('retired',restored.upload.state['phase'])
        self.assertEqual('primary-chosen',self.f.picker.state['phase']);self.assertEqual({self.foreign},set(self.b.reads.data));self.assertFalse(self.b.root.exists())
        events=self.b.host_state['bundleInfo']['serviceEvents'];self.assertEqual(['rename','delete'],[event['operation'] for event in events if event['kind']=='mapping-started'])
        self.assertLessEqual(len(restored.upload.state['frames']),160)

    def test_lost_read_selection_and_rename_recover_once_then_ignored_delete_remains_owned(self):
        owner=self.start();self.b.reads.lost='inventory'
        with self.assertRaises(NativeUIError):owner.browse()
        inventory_starts=sum(query['operation']=='inventory' for query in self.b.reads.requests)
        owner=self.f.tree_owner(self.f.owner());self.b.configure(lost='assets.tree.row.1')
        with self.assertRaises(NativeUIError):owner.finish_browse()
        inputs=len(self.b.inputs);owner=self.f.tree_owner(self.f.owner());owner.finish_browse()
        self.assertEqual(inputs,len(self.b.inputs));self.assertEqual(inventory_starts,sum(query['operation']=='inventory' for query in self.b.reads.requests))
        self.b.configure(lost='assets.rename.accept')
        with self.assertRaises(NativeUIError):owner.rename()
        command=next(entry['command']['commandId'] for entry in owner.state['inputs'] if entry['slot']=='confirm-rename')
        owner=self.f.tree_owner(self.f.owner());owner.finish_rename()
        self.assertEqual(1,sum(value['commandId']==command for value in self.b.inputs));self.assertEqual('renamed',owner.state['phase'])
        self.b.configure(ignore='assets.delete.accept')
        with self.assertRaises(NativeUIError):owner.delete()
        inputs=len(self.b.inputs)
        with self.assertRaises(NativeUIError):owner.finish_delete()
        self.assertEqual(inputs,len(self.b.inputs));pending=next(entry for entry in owner.state['inputs'] if entry['slot']=='confirm-delete')
        self.assertIsNotNone(pending['receipt']);self.assertIsNone(pending['resolvedBy']);self.assertEqual('deleting',owner.state['phase'])
        owner.close_clients();self.assertIsNotNone(pending['abandonedBy']);self.assertIsNotNone(owner.state['clientClosedBy'])
        clocks=len(self.b.native_clock.commands);observed=inspect_directory(self.path)
        self.assertEqual(['server-retirement'],observed[0]['responsibilities']);self.assertEqual(clocks,len(self.b.native_clock.commands))
        self.assertEqual({self.foreign,'/renamed-'+RUN+'/main.gltf','/renamed-'+RUN+'/mesh/triangle.bin','/renamed-'+RUN+'/textures/checker.png'},set(self.b.reads.data))
        self.assertEqual(['rename'],[event['operation'] for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='mapping-started'])

    def test_runtime_composes_mapping_flow_and_historical_successor_without_retiring_server(self):
        # Only the candidate/source factory is an explicit boundary model.
        # Existing AssetsRuntimeTests separately exercise its actual canonical
        # candidate, HTTP/AFC, native-clock factory and final transport guards.
        upload=self.f.owner();tree=self.f.tree_owner(upload)
        runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.b.monotonic)
        parts=dict(owned_files=self.f.files,picker=self.f.picker,owned_replies=self.f.replies,upload=upload,tree=tree,check=upload.guard)
        with patch.object(runtime,'_assets_components',return_value=parts):
            result=runtime._assets_mapping_readback('test-only',RUN,'primary',self.f.files.url,'b'*32,self.f.lock)
        self.assertEqual([self.foreign],[row['path'] for row in result['mappings']]);self.assertEqual([],runtime.cleanup_errors)
        self.assertEqual('deleted',tree.state['phase']);self.assertIsNotNone(tree.state['clientClosedBy']);self.assertEqual('primary-chosen',self.f.picker.state['phase'])
        clocks=len(self.b.native_clock.commands);rows=inspect_directory(self.path)
        self.assertEqual(['server-retirement'],rows[0]['responsibilities']);self.assertEqual(clocks,len(self.b.native_clock.commands))
