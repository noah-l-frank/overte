"""Shared normal page/picker originals, declared native/Qt host boundaries.

These counters prove local ownership behavior only, not upload/import effects,
actual devices, SDK lifetime or whole-end eligibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack
from ios.adapters.assets_episodes import PLAN
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.self_tests.assets_shared_page_fixture import Fixture


class AssetsPageLeaseTests(unittest.TestCase):
    def setUp(self):self.f=Fixture(self)
    def ticket(self,index):return format(index,'032x')
    def cycle(self,index):
        scope=self.f.begin(index,self.ticket(index))
        with scope.held():
            picker=self.f.picker(scope);picker.open_page();picker.open_picker();picker.choose_primary();picker.cancel_owned();picker.retire_inputs()
        return scope,picker
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical/readback may not acquire, write or retire')
    def cold(self):
        return OwnedAssetsPageLease(self.f.episodes,self.f.page.store,self.f.h.locks['primary'],pickers=self.f.pickers,historical=True,
            monotonic=self.f.boundary.monotonic)
    def test_five_normal_picker_roots_share_one_actual_page_until_final_home_and_cold_history_is_pure(self):
        original=None;pickers=[]
        for index in range(1,len(PLAN)+1):
            scope,picker=self.cycle(index);pickers.append(picker.state['picker'])
            page=self.f.page.identity()
            if original is None:original=page
            self.assertEqual(original,page);self.assertTrue(self.f.boundary.host_state['pageAlive'])
            self.assertEqual('retired',picker.files.state['phase']);self.assertEqual('page-borrowed-retired',picker.state['phase'])
            ui=self.f.boundary.ui();self.assertTrue(all(not row['alive'] for row in ui['roots'] if row['role']=='picker'))
            if index==len(PLAN):
                with scope.held():self.f.page.close(scope,picker)
        self.assertEqual(5,len(set(pickers)));self.assertEqual('closed',self.f.page.state['phase']);self.assertFalse(self.f.boundary.host_state['pageAlive'])
        commands=self.f.boundary.inputs
        # Original normal menu/page inputs occur only in episode1; final Home
        # occurs once in episode5. No close/reopen handoff is hidden here.
        self.assertEqual(1,sum(entry['slot']=='open-assets' for picker in self.f.pickers.values() for entry in picker.state['inputs']))
        self.assertEqual(1,sum(entry['slot']=='close-assets-page' for picker in self.f.pickers.values() for entry in picker.state['inputs']))
        before={str(p):(p.read_bytes(),p.stat().st_ino) for root in self.f.h.roots.values() for p in root.rglob('*') if p.is_file()}
        with ExitStack() as held:
            for scope in self.f.scopes:held.enter_context(scope.held())
            held.enter_context(patch.object(self.f.boundary,'exchange',side_effect=self.forbidden))
            held.enter_context(patch.object(PrivateFeatureState,'write',side_effect=self.forbidden))
            owner=self.cold();self.assertEqual(self.f.page.state,owner.state)
            for ref in owner.state['records']:owner.read(ref)
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for root in self.f.h.roots.values() for p in root.rglob('*') if p.is_file()})
        self.assertEqual(commands,self.f.boundary.inputs)
    def test_final_close_requires_all_five_ready_episodes_not_current_completed_prefix(self):
        scope,picker=self.cycle(1);before=len(self.f.boundary.inputs)
        with scope.held(),self.assertRaises(NativeUIError):self.f.page.close(scope,picker)
        self.assertTrue(self.f.boundary.host_state['pageAlive']);self.assertEqual(before,len(self.f.boundary.inputs));self.assertEqual('open',self.f.page.state['phase'])
    def test_new_picker_birth_keeps_prior_actual_weak_root_dead_and_initial_page_identity(self):
        _first,old=self.cycle(1);scope=self.f.begin(2,self.ticket(2))
        with scope.held():
            new=self.f.picker(scope);new.open_page();new.open_picker();ui=self.f.boundary.ui()
            rows={row['rootId']:row for row in ui['roots']};self.assertFalse(rows[old.state['picker']]['alive'])
            self.assertTrue(rows[new.state['picker']]['alive']);self.assertNotEqual(old.state['picker'],new.state['picker'])
            self.assertEqual(old.state['page'],new.state['page']);new.cancel_owned();new.retire_inputs()
    def test_saved_original_lost_parent_commit_recovers_without_new_ui_or_native_query(self):
        scope=self.f.begin(1,self.ticket(1))
        with scope.held():
            picker=self.f.picker(scope);actual=self.f.page.save
            def lose_parent_commit():
                if self.f.page.state['pending'] is None and self.f.page.state['records']:
                    raise NativeUIError('Modeled parent commit loss after actual saved original')
                return actual()
            with patch.object(self.f.page,'save',side_effect=lose_parent_commit):
                with self.assertRaises(NativeUIError):picker.open_page()
            value=self.f.page.store.read();state=unpack(value['payload'])[0]
            self.assertEqual('saved',state['pending']['original']['phase']);self.assertEqual([],state['records'])
            cold=OwnedAssetsPageLease(self.f.episodes,self.f.page.store,self.f.h.locks['primary'],pickers=self.f.pickers,monotonic=self.f.boundary.monotonic)
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):ref=cold.recover_capture()
            self.assertEqual(1,len(cold.state['records']));self.assertEqual(ref,cold.state['origin']);self.assertIsNone(cold.state['pending'])
    def test_planned_source_prefix_remains_owned_and_is_not_relabelled_complete_or_replayed(self):
        scope=self.f.begin(1,self.ticket(1))
        with scope.held():
            picker=self.f.picker(scope);actual=self.f.page.originals.intent
            def interrupted(kind,reference):
                result=actual(kind,reference)
                if reference['phase']=='planned':raise NativeUIError('Modeled interruption before immutable source open')
                return result
            with patch.object(self.f.page.originals,'intent',side_effect=interrupted):
                with self.assertRaises(NativeUIError):picker.open_page()
            before=self.f.page.store.path.read_bytes();cold=OwnedAssetsPageLease(self.f.episodes,self.f.page.store,self.f.h.locks['primary'],pickers=self.f.pickers,monotonic=self.f.boundary.monotonic)
            self.assertEqual('planned',cold.state['pending']['original']['phase'])
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
                with self.assertRaises(NativeUIError):cold.recover_capture()
            self.assertEqual(before,cold.store.path.read_bytes());self.assertEqual('reserved',cold.state['phase'])
    def test_transfer_cannot_be_claimed_from_pre_retirement_attachment_original(self):
        scope,picker=self.cycle(1)
        with scope.held():
            value=deepcopy(self.f.page.previous);state=unpack(value['payload'])[0]
            state['transfers']['1']=state['attachments']['1'];value['payload']=pack([state]);self.f.page.store.write(value,self.f.page.previous)
            with self.assertRaises(NativeUIError):self.cold()
            self.f.page.store.write(self.f.page.previous,value)

    def test_retired_files_without_retired_picker_refuse_direct_transfer_before_capture_or_save(self):
        scope=self.f.begin(1,self.ticket(1))
        with scope.held():
            picker=self.f.picker(scope);picker.open_page();picker.open_picker();picker.choose_primary();picker.cancel_owned();picker.files.release()
            self.assertEqual('retired',picker.files.state['phase']);self.assertEqual('picker-closed',picker.state['phase'])
            before=self.f.page.store.path.read_bytes();captures=len(picker.state['captures'])
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
                with self.assertRaises(NativeUIError):self.f.page.transferred(scope,picker)
            self.assertEqual(before,self.f.page.store.path.read_bytes());self.assertEqual(captures,len(picker.state['captures']))
            self.assertNotIn('1',self.f.page.state['transfers'])
    def test_changed_parent_custody_refuses_before_any_new_original_ui_capture(self):
        scope,picker=self.cycle(1)
        with scope.held():
            foreign=deepcopy(self.f.page.previous);state=unpack(foreign['payload'])[0];state['token']='f'*64;foreign['payload']=pack([state])
            self.f.page.store.write(foreign,self.f.page.previous);captures=len(picker.state['captures'])
            try:
                with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
                    with self.assertRaises(NativeUIError):self.f.page.capture(scope,picker)
                self.assertEqual(captures,len(picker.state['captures']));self.assertEqual(foreign,self.f.page.store.read())
            finally:self.f.page.store.write(self.f.page.previous,foreign)


if __name__=='__main__':unittest.main()
