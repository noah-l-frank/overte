"""Normal Assets picker/Runtime continuation with original QML and real files.

Native/candidate/SDK are declared models. This uses the genuine existing typed
parts seam, not a whole public Assets/Pool/byte/GPU or paired end qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from ios.adapters.assets_controls import project
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests.assets_upload_fixture import Fixture
from ios.self_tests.assets_picker_fixture import RUN,TICKET,URL,BINDING


class AssetsPickerPrepareRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name);self.root.chmod(0o700);self.f=Fixture(self.root);self.addCleanup(self.f.close)
        self.runtime=object.__new__(IOSAssetsRuntime);self.runtime.monotonic=self.f.boundary.monotonic
        self.parts=dict(owned_files=self.f.files,picker=self.f.picker,owned_replies=self.f.replies,upload=self.f.owner())

    def prepare(self):
        return self.runtime._assets_prepare_upload('declared-existing-parts',RUN,'primary',URL,TICKET,self.f.lock,
            resource='gltf-bundle/main.gltf',parts=self.parts)

    def reopen(self):
        self.f.picker=OwnedAssetsPicker(self.f.input,self.f.files,self.f.picker_store,BINDING,lock=self.f.lock,
            monotonic=self.f.boundary.monotonic,sleep=self.f.boundary.sleep)
        self.parts['picker']=self.f.picker
        # The normal upload parent uses the same literal child ownership.
        self.parts['upload']=self.f.owner()

    def assert_once(self):
        entries=self.f.picker.state['inputs'];commands=[row['command']['commandId'] for row in entries]
        self.assertEqual(len(commands),len(set(commands)));self.assertEqual(len(commands),len(self.f.boundary.inputs))
        self.assertEqual('primary-chosen',self.f.picker.state['phase']);self.assertEqual('ready',self.parts['upload'].state['phase'])
        count=len(self.f.boundary.inputs);self.prepare();self.assertEqual(count,len(self.f.boundary.inputs))

    def test_actual_runtime_prepares_genuine_normal_slots_and_repeated_call_never_delivers_again(self):
        self.prepare();self.assert_once()

    def test_lost_open_assets_reply_reopens_same_owner_and_observes_original_effect_without_resend(self):
        self.f.boundary.configure(lost='assets.open')
        with self.assertRaises(NativeUIError):self.prepare()
        entry=self.f.picker.state['inputs'][-1];command=deepcopy(entry['command']);self.assertIsNone(entry['receipt'])
        self.reopen();self.prepare();self.assert_once()
        matches=[row for row in self.f.boundary.inputs if row['commandId']==command['commandId']]
        self.assertEqual(1,len(matches));self.assertIsNotNone(next(row for row in self.f.picker.state['inputs'] if row['command']==command)['resolvedBy'])

    def test_lost_open_picker_reply_resolves_actual_original_then_continues_folder_and_primary(self):
        self.f.boundary.configure(lost='assets.upload')
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual('page-open',self.f.picker.state['phase']);command=deepcopy(self.f.picker.state['inputs'][-1]['command'])
        self.reopen();self.prepare();self.assert_once()
        self.assertEqual(1,sum(row['commandId']==command['commandId'] for row in self.f.boundary.inputs))

    def test_foreign_page_after_completed_menu_before_owned_open_is_not_adopted(self):
        actual=self.f.picker.input
        def interrupted(slot,*args,**kwargs):
            result=actual(slot,*args,**kwargs)
            if slot=='open-edit-menu':raise OSError('Original menu reply saved; caller interrupted before Assets open')
            return result
        with patch.object(self.f.picker,'input',side_effect=interrupted),self.assertRaises(OSError):self.prepare()
        # Independent test stimulus uses the genuine ordinary native UI source,
        # outside this owner's open-assets intent. It is never adapter cleanup.
        self.f.input.assets_input('assets.open','activate',reference=project(self.f.input.capture()))
        before=deepcopy(self.f.boundary.inputs);self.reopen()
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual(before,self.f.boundary.inputs)
        self.assertEqual(['open-edit-menu'],[row['slot'] for row in self.f.picker.state['inputs']])
        self.assertIsNone(self.parts['upload'].state)

    def test_ignored_replace_with_successful_receipt_cannot_submit_folder_or_become_ready(self):
        actual=self.f.picker.input
        def ignored_replace(slot,*args,**kwargs):
            if slot=='replace-folder':self.f.boundary.configure(ignore='asset-file.folder')
            return actual(slot,*args,**kwargs)
        # The original-QML host ignores this one ordinary replace delivery but
        # returns the native transport's normal performed receipt. The genuine
        # independent control observation must still block the later submit.
        with patch.object(self.f.picker,'input',side_effect=ignored_replace),self.assertRaises(NativeUIError):self.prepare()
        row=self.f.picker.state['inputs'][-1]
        self.assertEqual('replace-folder',row['slot']);self.assertIsNotNone(row['receipt'])
        self.assertTrue(row['receipt']['status']['performed'])
        self.assertNotIn('submit-folder',[entry['slot'] for entry in self.f.picker.state['inputs']])
        self.assertIsNone(self.parts['upload'].state);before=deepcopy(self.f.boundary.inputs)
        self.reopen()
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual(before,self.f.boundary.inputs)
        self.assertEqual('picker-open',self.f.picker.state['phase']);self.assertIsNone(self.parts['upload'].state)

    def test_ignored_open_is_not_an_observed_effect_and_never_replayed_or_grants_ready_upload(self):
        self.f.boundary.configure(ignore='assets.open',lost='assets.open')
        with self.assertRaises(NativeUIError):self.prepare()
        before=deepcopy(self.f.boundary.inputs);self.reopen()
        with self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual(before,self.f.boundary.inputs);self.assertIsNone(self.parts['upload'].state)
        self.assertIsNone(self.f.picker.state['inputs'][-1]['resolvedBy']);self.assertEqual('reserved',self.f.picker.state['phase'])


if __name__=='__main__':unittest.main()
