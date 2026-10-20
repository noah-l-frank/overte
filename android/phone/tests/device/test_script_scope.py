"""Host-only schema transfer with original readers and private file ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from overte_phone_script_scope import transfer_file_scope
from overte_phone_script_files import PhoneScriptFileIO
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from self_tests import test_normal_script_file_manager as files
from self_tests.test_native_script_observation import Boundary as Execution, effect_source, code_source
from self_tests.test_native_script_membership import membership_source,manager as known_manager
from self_tests.test_native_script_loads import history
from self_tests.test_script_ui_inventory import inventory,picker
from self_tests.test_script_manager_status import observed
from script_file_native_boundary import FileNativeBoundary


class ScriptScopeTests(unittest.TestCase):
    flow=files.ScriptFileManagerTests.flow
    opened=files.ScriptFileManagerTests.opened

    def setUp(self):
        files.ScriptFileManagerTests.setUp(self)
        original=self.native.observe
        def observed_at_native_clock(after):
            packet,_epoch=original(after)
            packet['sampleEpochMs']=20000
            return packet,20000
        self.native.observe=observed_at_native_clock
        self.manager=self.opened();self.manager.file_picker_choose('script-bundle/main.js')
        self.manager.stop_source(self.directory+'/script-bundle/main.js')
        self.execution=Execution()
        def empty(packet):
            packet['instance']='d'*32;packet['source']['engines']=[]
            code_source(packet);effect_source(packet);packet['source']['effects'].update(entities=[],scannedEntities=0)
            history(packet,[]);membership_source(packet)
        self.execution.mutate=empty;self.reader=self.execution.reader()
        self.ui_source=FileNativeBoundary(self.storage.root)
        def visual(packet):
            packet['scriptInventory']=inventory([observed(statusText='Stopping main.js',labelText='Stopping main.js',
                rootVisible=self.native.manager,labelVisible=self.native.manager)],tabletShown=self.native.tablet)
        self.ui_source.mutate=visual
        self.ui=PhoneScriptFileIO(self.ui_source.send,lambda:json.dumps(self.ui_source.value),lambda:20000,
            lambda:True,31,monotonic=lambda:self.ui_source.ui.clock,sleep=self.ui_source.ui.sleep)

    def transfer(self):return transfer_file_scope(files.RUN,self.manager,self.reader,self.ui)

    def missing(self):
        return NormalScriptManager(self.native,self.native.observe,self.native.store,files.BINDING,
            source_kind='feature-script-missing',monotonic=lambda:self.native.clock,sleep=self.native.sleep)

    def test_explicit_transfer_preserves_actual_open_ui_flags_and_separate_original_files_without_input(self):
        before=list(self.native.calls);owner=deepcopy(self.files.store.read())
        result=self.transfer()
        self.assertEqual(before,self.native.calls);self.assertEqual([],self.ui_source.input_requests)
        self.assertTrue(self.native.tablet and self.native.manager)
        self.assertEqual(owner,self.files.store.read());self.assertTrue(self.storage.root.exists())
        self.assertEqual('feature-script-missing',result['sourceKind']);self.assertEqual(4,result['schemaVersion'])
        self.assertTrue(result['tabletOwned'] and result['managerOwned']);self.assertIsNone(result['source'])
        self.assertEqual(self.manager.state['afterSequence'],result['afterSequence'])
        self.assertEqual(self.manager.state['observerInstance'],result['observerInstance'])
        missing=self.missing();missing.open()
        self.assertEqual(before,self.native.calls) # No close/reopen to change host schema.

    def test_retired_old_scope_object_cannot_click_close_cancel_reopen_or_overwrite_new_scope(self):
        self.transfer();before=list(self.native.calls);saved=self.native.store.read()
        for action in (self.manager.close,self.manager.close_tablet,self.manager.close_dialog,
                       self.manager.open,self.manager.file_picker_open,self.manager.file_picker_cancel,
                       lambda:self.manager.stop_source(self.directory+'/script-bundle/main.js')):
            with self.subTest(action=action),self.assertRaises(NativeUIError):action()
        self.assertEqual(before,self.native.calls);self.assertEqual(saved,self.native.store.read())

    def test_ordinary_missing_constructor_still_refuses_implicit_schema_adoption(self):
        before=self.native.store.read()
        with self.assertRaises(NativeUIError):self.missing()
        self.assertEqual(before,self.native.store.read())

    def test_active_pending_or_orphan_effect_keeps_file_scope_and_never_closes_product_ui(self):
        original=self.execution.mutate
        for fault in ('pending','engine','effect'):
            def retained(packet):
                original(packet)
                if fault=='pending':membership_source(packet,[known_manager('5'*32,self.directory+'/script.js')],1)
                elif fault=='engine':
                    engine=deepcopy(self.execution.engine);engine['url']=self.directory+'/script-bundle/main.js'
                    packet['source']['engines']=[engine];code_source(packet);membership_source(packet)
                else:
                    effect_source(packet);row=packet['source']['effects']['entities'][0]
                    row.update(name='e2e-'+files.RUN+'-script',userData=json.dumps(dict(runId=files.RUN,ticks=2)))
            self.execution.mutate=retained;self.reader=self.execution.reader();before=list(self.native.calls)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.transfer()
            self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])
            self.assertEqual(before,self.native.calls)

    def test_closed_picker_or_pending_system_ui_cannot_be_repaired_by_transfer(self):
        original=self.ui_source.mutate
        for fault in ('closed','picker','system'):
            def wrong(packet):
                original(packet)
                if fault=='closed':packet['scriptInventory']['tabletShown']=False
                else:packet['scriptInventory']['pickers']=[picker(visible=fault=='picker',requestId='pending' if fault=='system' else '')]
            self.ui_source.mutate=wrong
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.transfer()
            self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])

    def test_changed_original_fixture_bytes_block_mode_change_before_new_execution_request(self):
        self.storage.fault='changed-byte';before=len(self.execution.commands)
        with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual(before,len(self.execution.commands));self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])

    def test_same_pid_foreign_native_birth_is_not_a_file_scope_transfer(self):
        original=self.execution.mutate
        def foreign(packet):original(packet);packet['instance']='f'*32
        self.execution.mutate=foreign
        with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])

    def test_foreign_run_cannot_adopt_current_file_scope_or_trigger_original_native_query(self):
        before=len(self.execution.commands)
        with self.assertRaises(NativeUIError):transfer_file_scope('e'*32,self.manager,self.reader,self.ui)
        self.assertEqual(before,len(self.execution.commands))
        self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])

    def test_lost_private_cas_return_preserves_new_ownership_and_never_replays_product_input(self):
        original=self.native.store.write;before=list(self.native.calls)
        def lost(value,previous):original(value,previous);raise RuntimeError('synthetic lost private write receipt')
        with patch.object(self.native.store,'write',side_effect=lost):
            with self.assertRaises(NativeUIError):self.transfer()
        # sample_full's first journal write was lost before the schema CAS.
        self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])
        self.assertEqual(before,self.native.calls)

    def test_lost_completed_schema_cas_is_retained_and_stale_scope_cannot_repeat_it(self):
        original=self.native.store.write;before=list(self.native.calls)
        def lost(value,previous):
            original(value,previous)
            if value['sourceKind']=='feature-script-missing':raise RuntimeError('synthetic lost CAS completion')
        with patch.object(self.native.store,'write',side_effect=lost):
            with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual('feature-script-missing',self.native.store.read()['sourceKind'])
        with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual(before,self.native.calls)

    def test_whole_deadline_includes_native_proof_before_private_schema_mutation(self):
        original=self.execution.mutate
        def late(packet):original(packet);self.native.clock=21
        self.execution.mutate=late
        with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual('script-file-bundle',self.native.store.read()['sourceKind'])

    def test_late_private_cas_keeps_transferred_ownership_but_does_not_return_success(self):
        original=self.native.store.write
        def late(value,previous):
            original(value,previous)
            if value['sourceKind']=='feature-script-missing':self.native.clock=21
        with patch.object(self.native.store,'write',side_effect=late):
            with self.assertRaises(NativeUIError):self.transfer()
        self.assertEqual('feature-script-missing',self.native.store.read()['sourceKind'])


if __name__=='__main__':unittest.main()
