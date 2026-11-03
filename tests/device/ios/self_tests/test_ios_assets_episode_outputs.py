"""Actual original namespaces and lock/WAL counterexamples, no product facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from ios.adapters.script_runtime import IOSScriptRuntime
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_episodes import AssetsEpisodes, PLAN
from ios.adapters.assets_files import IOSAssetsFiles
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles, SelectedAssetsFiles
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests.test_ios_assets_selected_end_profile import AssetsSelectedEndProfileTests
from ios.self_tests.assets_picker_fixture import BINDING, RUN, TICKET, URL


class AssetsEpisodeOutputsTests(unittest.TestCase):
    def setUp(self):
        self.h=AssetsSelectedEndProfileTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.selected=self.h.archive();self.selected.select()
        self.owner=AssetsEpisodes(self.selected,self.h.locks)

    def files(self,scope):
        native=IOSAssetsFiles(self.h.no_native,self.h.no_native,lambda:1900000000000,lambda:True,42,monotonic=lambda:0.,sleep=self.h.no_native)
        store=PrivateFeatureState(Path(scope.descriptor['directories']['primary']['stateRoot']['path'])/('ios-assets-'+RUN+'-primary-files.json'))
        return EpisodeAssetsFiles(native,store,BINDING,RUN,URL,lock=scope.locks['primary'],selection=self.selected,episode=scope)

    def test_five_distinct_episode_outputs_retain_every_prior_original_and_actual_run_role(self):
        scopes=[];previous={}
        for index,(_kind,resource) in enumerate(PLAN,1):
            scope=self.owner.begin(index,TICKET);scopes.append(scope)
            with scope.held():
                owner=self.files(scope);owner.reserve(TICKET,resource)
                self.assertEqual(4,owner.previous['iosAssetsFileOwnerVersion'])
                self.assertEqual(RUN,owner.previous['runId']);self.assertEqual('primary',owner.previous['role'])
                self.assertEqual(scope.link(),owner.previous['episode'])
                self.assertEqual(self.selected.link(),owner.previous['selectedPair'])
            for path,(body,inode) in previous.items():
                self.assertEqual((body,inode),(path.read_bytes(),path.stat().st_ino))
            previous={p:(p.read_bytes(),p.stat().st_ino) for root in self.h.roots.values() for p in root.rglob('*') if p.is_file() and p!=self.owner.store.path}
        self.assertEqual(20,len({row['path'] for scope in scopes for roots in scope.descriptor['directories'].values() for row in roots.values()}))
        cold=AssetsEpisodes(self.h.archive(),self.h.locks)
        for index in range(1,6):self.assertEqual(scopes[index-1].link(),cold.scope(index).link())
        self.assertEqual([],self.h.native_calls)

    def test_output_path_changes_only_assets_child_stores_and_keeps_sdk_state_path_canonical(self):
        scope=self.owner.begin(1,TICKET)
        class Adapter:
            def _candidate_guard(self):pass
            def _binding(self,*args):raise AssertionError('No installed binding may be acquired by output-path planning')
            def state_path(_self,selector):return self.h.roots[selector]/'session.json'
        runtime=IOSAssetsRuntime(Adapter(),episode=scope)
        self.assertEqual(self.h.roots['primary']/'session.json',runtime.state_path('primary'))
        with scope.held():
            path=runtime._assets_store('primary',RUN,'primary','files').path
            self.assertEqual(Path(scope.descriptor['directories']['primary']['stateRoot']['path']),path.parent)
            self.assertNotEqual(runtime.state_path('primary').parent,path.parent)
        self.assertEqual([],self.h.native_calls)

    def test_same_body_foreign_original_inode_blocks_cold_reopen_and_new_owner_before_native(self):
        scope=self.owner.begin(1,TICKET);wire=scope.original;path=self.owner.originals.path(wire)
        raw=path.read_bytes();path.rename(path.with_name('retained-original-before-foreign-inode'))
        path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner.scope(1)
        with self.assertRaises(NativeUIError):AssetsEpisodes(self.h.archive(),self.h.locks)
        self.assertEqual([],self.h.native_calls)

    def test_replaced_empty_directory_inode_cannot_be_adopted_as_an_episode_output(self):
        scope=self.owner.begin(1,TICKET)
        path=Path(scope.descriptor['directories']['actor']['artifactRoot']['path']);path.rename(path.with_name('retained-empty-episode-before-replacement'))
        path.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):scope.guard()
        self.assertEqual([],self.h.native_calls)

    def test_uncertain_directory_birth_retains_planned_responsibility_and_never_adopts_foreign_inode(self):
        actual=self.owner.save;count=0
        def lose_saved_birth():
            nonlocal count
            count+=1
            if count==2:raise NativeUIError('Declared WAL failure after actual mkdir before original inode return')
            return actual()
        self.owner.save=lose_saved_birth
        with self.assertRaises(NativeUIError):self.owner.begin(1,TICKET)
        value=self.owner.store.read();self.assertEqual('planned',value['entries'][0]['phase'])
        self.assertIsNone(value['entries'][0]['directories']['primary']['stateRoot']['identity'])
        self.assertTrue(self.owner.path(1,'primary','stateRoot').is_dir())
        before=self.owner.store.path.read_bytes()
        with self.assertRaises(NativeUIError):AssetsEpisodes(self.h.archive(),self.h.locks)
        self.assertEqual(before,self.owner.store.path.read_bytes());self.assertEqual([],self.h.native_calls)

    def test_skipped_reused_or_boolean_episode_index_refuses_before_output_birth(self):
        for index in (2,True):
            with self.assertRaises(NativeUIError):self.owner.begin(index,TICKET)
        self.assertIsNone(self.owner.store.read())
        self.owner.begin(1,TICKET);before=self.owner.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.owner.begin(1,TICKET)
        self.assertEqual(before,self.owner.store.path.read_bytes());self.assertEqual([],self.h.native_calls)

    def test_foreign_episode_link_and_literal_selected_reader_cannot_adopt_files_four(self):
        scope=self.owner.begin(1,TICKET)
        with scope.held():
            files=self.files(scope);files.reserve(TICKET)
            before=files.store.path.read_bytes();value=deepcopy(files.previous);value['episode']['index']=2
            files.store.write(value,files.previous)
            with self.assertRaises(NativeUIError):self.files(scope)
            files.store.write(files.previous,value)
            with self.assertRaises(NativeUIError):SelectedAssetsFiles(files.native,files.store,BINDING,RUN,URL,lock=scope.locks['primary'],selection=self.selected)
            self.assertEqual(before,files.store.path.read_bytes())
        self.assertEqual([],self.h.native_calls)

    def test_both_actual_lock_domains_are_required_and_unknown_selector_refuses(self):
        scope=self.owner.begin(1,TICKET)
        class Runtime:
            def state_path(_self,selector):return self.h.roots[selector]/'session.json'
        runtime=Runtime()
        with self.assertRaises(NativeUIError):scope.runtime_guard(runtime,'primary',scope.locks['primary'])
        with scope.held():
            self.assertTrue(scope.runtime_guard(runtime,'primary',scope.locks['primary'],BINDING))
            with self.assertRaises(NativeUIError):scope.runtime_guard(runtime,'primary',scope.locks['actor'],BINDING)
            with self.assertRaises(NativeUIError):scope.role('unselected-target')
        self.assertEqual([],self.h.native_calls)

    def test_unknown_episode_namespace_blocks_before_any_later_birth_or_source(self):
        self.owner.begin(1,TICKET)
        path=self.h.roots['actor']/'assets-episode-foreign-owner';path.mkdir(mode=0o700)
        before=self.owner.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.owner.begin(2,TICKET)
        self.assertEqual(before,self.owner.store.path.read_bytes());self.assertEqual([],self.h.native_calls)

    def test_previous_episode_cannot_acquire_sources_after_next_begin_but_original_history_stays_readable(self):
        first=self.owner.begin(1,TICKET)
        class Adapter:
            def _candidate_guard(self):pass
            def _binding(_self,*args):return self.h.no_native(*args)
            def state_path(_self,selector):return self.h.roots[selector]/'session.json'
        runtime=IOSAssetsRuntime(Adapter(),episode=first)
        with first.held():
            files=self.files(first);files.reserve(TICKET)
            previous=deepcopy(files.previous);path=files.store.path;body=path.read_bytes();inode=path.stat().st_ino
            link=first.link();self.assertTrue(first.runtime_guard(runtime,'primary',first.locks['primary'],BINDING))
        second=self.owner.begin(2,'d'*32)
        with first.held():
            # Actual existing factory boundaries, before the base SDK factory.
            with patch.object(IOSScriptRuntime,'_sources',side_effect=self.h.no_native) as source_factory:
                with self.assertRaises(NativeUIError):runtime._sources('primary')
                with self.assertRaises(NativeUIError):runtime._assets_sources('primary',first.locks['primary'])
                self.assertEqual(0,source_factory.call_count)
            self.assertTrue(first.guard());self.assertEqual(link,first.link())
            self.assertEqual(previous,self.files(first).previous)
            self.assertEqual((body,inode),(path.read_bytes(),path.stat().st_ino))
        current=IOSAssetsRuntime(Adapter(),episode=second)
        with second.held():self.assertTrue(second.runtime_guard(current,'primary',second.locks['primary'],BINDING))
        cold=AssetsEpisodes(self.h.archive(),self.h.locks)
        self.assertEqual(link,cold.scope(1).link());self.assertEqual([],self.h.native_calls)
