"""Narrow Assets owner through original QML JS and actual host input files.

Qt/UIKit/lifetime/native acquisition boundaries are explicit models. This
suite cannot establish a compiled/installed/native/server/device capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.script_feature.history import pack
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_files as files
from ios.adapters.assets_controls import project,same_reference
from ios.adapters.assets_picker import ERROR,OwnedAssetsPicker
from ios.adapters.assets_budget import Budget
from ios.self_tests.assets_picker_fixture import Fixture,RUN,TICKET,URL,BINDING


class AssetsPickerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name);self.path.chmod(0o700);self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close)
        self.boundary=self.fixture.boundary;self.owner=self.fixture.picker

    def test_original_unavailable_error_retains_picker_then_cancel_close_and_original_companion_absence(self):
        value=self.fixture.unavailable();self.assertEqual('unavailable',self.owner.state['phase'])
        self.assertFalse((self.boundary.root/'main.gltf').exists());self.assertTrue((self.boundary.root/'mesh/triangle.bin').exists())
        picker=[row for row in value['source']['ui']['roots'] if row['role']=='picker'][0]
        self.assertEqual(ERROR,picker['error']);self.assertTrue(picker['alive']);self.assertFalse(picker['closing'])
        self.assertEqual(0,self.boundary.host_state['selectedBundles']);self.assertEqual(0,self.boundary.host_state['destinationCalls']);self.assertEqual(0,self.boundary.host_state['uploads'])
        self.owner.cancel();self.assertEqual(1,self.boundary.host_state['canceled']);self.owner.close_page();last=self.owner.release()
        self.assertEqual({'exists':False,'files':[]},last['source']['files']);self.assertFalse(self.boundary.root.exists())
        self.assertEqual('retired',self.owner.state['phase']);self.assertIsNotNone(self.fixture.picker_store.read());self.assertIsNotNone(self.fixture.file_store.read())
        for name in ('negativeWindow','cleanupWindow'):
            window=self.owner.state[name];self.assertGreaterEqual(len(window['requests']),2)
            self.assertGreaterEqual(window['hostBrackets'][-1]['before']-window['hostBrackets'][0]['after'],3)

    def test_ignored_real_normal_select_cannot_supply_unavailable_evidence(self):
        self.fixture.start();self.boundary.configure(ignore='asset-file.select')
        with self.assertRaises(NativeUIError):self.owner.retire_and_select()
        self.assertNotEqual('unavailable',self.owner.state['phase']);self.assertEqual('',self.boundary.host_state['ui']['error'])
        self.assertTrue(self.boundary.host_state['pickerAlive']);self.assertEqual(0,self.boundary.host_state['uploads'])

    def test_lost_cancel_return_recovers_original_weak_death_without_resending(self):
        self.fixture.unavailable();self.boundary.configure(lost='asset-file.cancel')
        with self.assertRaises(NativeUIError):self.owner.cancel()
        count=len(self.boundary.inputs);self.assertEqual('canceling',self.owner.state['phase'])
        recovered=OwnedAssetsPicker(self.fixture.input,self.fixture.files,self.fixture.picker_store,BINDING,lock=self.fixture.lock,
            monotonic=self.boundary.monotonic,sleep=self.boundary.sleep)
        recovered.recover_cancel();self.assertEqual(count,len(self.boundary.inputs));self.assertEqual(1,self.boundary.host_state['canceled'])
        recovered.close_page();recovered.release();self.assertEqual('retired',recovered.state['phase'])

    def test_deferred_actual_qml_destroy_is_not_a_closed_picker(self):
        self.fixture.unavailable();self.boundary.configure(hold=True)
        with self.assertRaises(NativeUIError):self.owner.cancel()
        self.assertTrue(self.boundary.host_state['pickerAlive']);self.assertTrue(self.boundary.host_state['ui']['closing'])
        self.assertEqual('canceling',self.owner.state['phase']);self.assertTrue((self.boundary.root/'mesh/triangle.bin').exists())
        self.boundary.configure(hold=False);self.owner.recover_cancel();self.assertEqual('picker-closed',self.owner.state['phase'])

    def test_real_weak_consumer_and_pending_callback_block_companion_release(self):
        self.fixture.unavailable();self.owner.cancel();self.owner.close_page();self.boundary.hold_consumer(pending=1)
        with self.assertRaises(NativeUIError):self.owner.release()
        self.assertTrue((self.boundary.root/'mesh/triangle.bin').exists());self.assertEqual('primary-retired',self.fixture.files.state['phase'])
        self.assertEqual(0,sum(row['operation']=='release' for row in self.boundary.requests))

    def test_lost_storage_return_recovers_by_observe_only(self):
        owner=self.fixture.files;owner.reserve(TICKET);self.boundary.lost='stage'
        with self.assertRaises(NativeUIError):owner.stage()
        recovered=files.OwnedAssetsFiles(self.boundary.files_native(),self.fixture.file_store,BINDING,RUN,URL,lock=self.fixture.lock)
        recovered.recover_stage();self.assertEqual(1,sum(row['operation']=='stage' for row in self.boundary.requests))
        with self.assertRaises(NativeUIError):recovered.stage()
        self.assertEqual('staged',recovered.state['phase'])

    def test_changed_original_bytes_never_release_owned_files(self):
        self.fixture.files.reserve(TICKET);self.fixture.files.stage();path=self.boundary.root/'mesh/triangle.bin';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaises(NativeUIError):self.fixture.files.release()
        self.assertTrue(path.exists());self.assertNotEqual('retired',self.fixture.files.state['phase'])

    def test_actual_hardlink_blocks_original_file_observation_and_release(self):
        self.fixture.files.reserve(TICKET);self.fixture.files.stage();path=self.boundary.root/'mesh/triangle.bin'
        alias=self.path/'foreign-alias.bin';alias.hardlink_to(path);self.assertEqual(2,path.stat().st_nlink)
        with self.assertRaises(NativeUIError):self.fixture.files.release()
        self.assertTrue(path.exists());self.assertTrue(alias.exists())
        self.assertEqual(0,sum(row['operation']=='release' for row in self.boundary.requests))

    def test_equal_replacement_bytes_are_not_the_original_sealed_inode(self):
        self.fixture.files.reserve(TICKET);self.fixture.files.stage();path=self.boundary.root/'mesh/triangle.bin'
        raw=path.read_bytes();old=path.stat();path.rename(self.path/'old-owned-input.bin');path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(old.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.fixture.files.observe()
        self.assertTrue(path.exists());self.assertEqual('staged',self.fixture.files.state['phase'])

    def test_foreign_source_window_token_and_stale_reference_block_normal_delivery(self):
        self.fixture.start();original=project(self.fixture.input.capture());identifier='asset-file.select'
        for key in ('token','windowId','componentSource'):
            current=deepcopy(original);row=next(row for row in current['controls'] if row['id']==identifier)
            if key=='token':row['token']='00000000-0000-0000-0000-000000000001'
            elif key=='windowId':row['assetControl'][key]='00000000-0000-0000-0000-000000000001'
            else:row['assetControl'][key]='qrc:/foreign.qml'
            with self.subTest(key=key),self.assertRaises((NativeUIError,ValueError)):same_reference(original,current,identifier)
        current=deepcopy(original);current['scope']['elapsedMs']+=1500;current['scope']['sampleEpochMs']+=1500
        with self.assertRaises(NativeUIError):same_reference(original,current,identifier)

    def test_coherent_short_native_span_rejects_despite_three_second_host_window(self):
        self.fixture.unavailable();window=deepcopy(self.owner.state['negativeWindow']);state=deepcopy(self.fixture.files.state)
        records={entry['query']['commandId']:entry['packet'] for entry in state['originals']};first=records[window['requests'][0]]
        base=deepcopy(first['clockBefore'])
        # Explicit negative native-clock model: every individual native bracket
        # and sequence remains coherent; its total span is under one second.
        # The independent retained host acquisition window stays above three.
        for index,request in enumerate(window['requests']):
            packet=records[request]
            for key in ('epochMs','monotonicMs'):
                packet['clockBefore'][key]=base[key]+index*10;packet['clockAfter'][key]=base[key]+index*10+1
                packet['source']['work']['clock'][key]=base[key]+index*10
            packet['source']['ui']['capturedEpochMs']=packet['clockBefore']['epochMs']
        envelope=self.fixture.file_store.read();envelope['payload']=pack([state]);self.fixture.files.decode(envelope)
        original=self.fixture.files.state;self.fixture.files.state=state
        try:
            self.owner._window_validate(window,self.owner.state,complete=False)
            self.assertGreaterEqual(window['hostBrackets'][-1]['before']-window['hostBrackets'][0]['after'],3)
            with self.assertRaises(NativeUIError):self.owner._window_validate(window,self.owner.state,complete=True)
        finally:self.fixture.files.state=original

    def test_outer_budget_is_one_sticky_twenty_second_host_clock(self):
        now=[0];budget=Budget(lambda:now[0]);now[0]=19.999;budget.check();now[0]=20
        with self.assertRaises(NativeUIError):budget.check()
        now[0]=1
        with self.assertRaises(NativeUIError):budget.check()


if __name__=='__main__':unittest.main()
