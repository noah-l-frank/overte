"""Independent current source/owner factory admission without SDK execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_shared_action_runtime import SharedActionAssetsRuntime
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles
from ios.adapters.assets_episodes import AssetsEpisodes
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.test_ios_assets_action_phase import AssetsActionPhaseTests
from ios.self_tests.assets_shared_page_client_fixture import Fixture
from ios.self_tests.assets_picker_fixture import RUN,URL,BINDING


class SharedActionFactoryTests(unittest.TestCase):
    def setUp(self):
        self.a=AssetsActionPhaseTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
    def runtime(self,scope,episode=None,page=None):
        test=self
        class Adapter:
            def state_path(_self,selector):return test.a.h.roots[selector]/'session.json'
            def _candidate_guard(_self):pass
            def _binding(_self,*args):return test.a.h.no_native(*args)
        return SharedActionAssetsRuntime(Adapter(),self.a.selected,assets_action=scope,phase=self.a.phase,episode=episode,page_lease=page)
    def test_expired_action1_cannot_acquire_sdk_sources_before_next_phase_or_canonical_output_use(self):
        ticket,row=self.a.activate(1);scope=self.a.owner.begin(1,ticket,row['verb'],row['inputs']);runtime=self.runtime(scope)
        self.assertEqual(self.a.h.roots['primary']/'session.json',runtime.state_path('primary'));self.a.activate(2)
        with patch.object(IOSScriptRuntime,'_sources',side_effect=self.a.h.no_native) as source:
            with self.assertRaises(NativeUIError):runtime._sources('primary')
            with self.assertRaises(NativeUIError):runtime._assets_sources('primary',self.a.h.locks['primary'])
            self.assertEqual(0,source.call_count)
        self.assertEqual([],self.a.h.native_calls)
    def test_factory_never_invents_future_bake_or_import_ticket_and_preserves_completed_actual_ticket(self):
        episodes=AssetsEpisodes(self.a.selected,self.a.h.locks);scope=None;current=None
        for index in range(1,19):
            ticket,row=self.a.activate(index);current=self.a.owner.begin(index,ticket,row['verb'],row['inputs'])
            if index in (2,4,14,18):scope=episodes.begin({2:1,4:2,14:3,18:4}[index],ticket)
            if index<18:self.a.owner.complete(current)
        page=OwnedAssetsPageLease(episodes,PrivateFeatureState(self.a.h.roots['primary']/('ios-assets-page-lease-'+RUN+'-primary.json')),
            self.a.h.locks['primary']);page.reserve()
        with scope.held():
            runtime=self.runtime(current,scope,page);lock=scope.locks['primary']
            with self.assertRaises(NativeUIError):runtime._assets_owner_values('baking','primary',RUN,'primary',lock)
            values=runtime._assets_owner_values('replies','primary',RUN,'primary',lock);self.assertIs(current,values['action'])
            self.a.owner.complete(current);ticket,row=self.a.activate(19);current=self.a.owner.begin(19,ticket,row['verb'],row['inputs']);self.a.owner.complete(current)
            ticket,row=self.a.activate(20);current=self.a.owner.begin(20,ticket,row['verb'],row['inputs']);runtime=self.runtime(current,scope,page)
            self.assertEqual(ticket,runtime._assets_owner_values('baking','primary',RUN,'primary',lock)['action_ticket'])
            with self.assertRaises(NativeUIError):runtime._assets_owner_values('parsed','primary',RUN,'primary',lock)
            self.a.owner.complete(current);import_ticket,row=self.a.activate(21);current=self.a.owner.begin(21,import_ticket,row['verb'],row['inputs']);runtime=self.runtime(current,scope,page)
            self.assertEqual(ticket,runtime._assets_owner_values('baking','primary',RUN,'primary',lock)['action_ticket'])
            self.assertEqual(import_ticket,runtime._assets_owner_values('parsed','primary',RUN,'primary',lock)['action_ticket'])
            self.assertEqual(format(18,'032x'),scope.descriptor['ticket']);self.assertEqual([],self.a.h.native_calls)


class PageCurrentRebindingTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture(self);self.f.cancel_episode(1);self.scope=self.f.begin(2,format(2,'032x'));held=self.scope.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.picker=self.f.picker(self.scope);self.picker.open_page();self.picker.open_picker();self.picker.choose_primary()
    def reopen(self):
        old=self.picker;files=EpisodeAssetsFiles(self.f.boundary.files_native(),old.files.store,BINDING,RUN,URL,lock=old.lock,
            selection=self.f.selected,episode=self.scope)
        return PageLeasePicker(self.f.boundary.native_input(),files,old.store,BINDING,lock=old.lock,page_lease=self.f.page,episode=self.scope,
            monotonic=self.f.boundary.monotonic,sleep=self.f.boundary.sleep)
    def test_fresh_owner_reassembly_uses_same_actual_metadata_and_page_without_reopening_or_retiming(self):
        before=deepcopy(self.f.boundary.inputs);old=self.picker;new=self.reopen()
        self.assertIsNot(old,new);self.assertIs(new,self.f.page.pickers[2]);self.assertEqual(old.previous,new.previous)
        self.assertEqual(old.files.previous,new.files.previous);self.assertEqual(before,self.f.boundary.inputs)
        new.cancel_owned();new.retire_inputs();self.assertTrue(self.f.boundary.host_state['pageAlive']);self.assertIn('2',self.f.page.state['transfers'])
    def test_stale_old_owner_snapshot_cannot_adopt_a_newly_advanced_picker_history_before_native_input(self):
        old=self.picker;new=self.reopen();new.capture();self.f.page.pickers[2]=old
        count=len(self.f.boundary.inputs);before=new.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.reopen()
        self.assertEqual(count,len(self.f.boundary.inputs));self.assertEqual(before,new.store.path.read_bytes());self.f.page.pickers[2]=new


if __name__=='__main__':unittest.main()
