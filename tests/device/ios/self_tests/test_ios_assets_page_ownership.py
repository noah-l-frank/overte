"""Actual shared page originals under SDK/query/write-free complete readers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_page_ownership import AssetsPageInventoryContext,inspect_page
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata,FrozenAssetsMetadata
from ios.self_tests.assets_shared_page_fixture import Fixture


class AssetsPageOwnershipTests(unittest.TestCase):
    def setUp(self):self.f=Fixture(self)
    def context(self):return AssetsPageInventoryContext(self.f.episodes,tuple(self.f.scopes))
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Pure page reader may not send/acquire/write')
    def cycle(self,index):
        scope=self.f.begin(index,format(index,'032x'))
        with scope.held():
            picker=self.f.picker(scope);picker.open_page();picker.open_picker();picker.choose_primary();picker.cancel_owned();picker.retire_inputs()
        return scope,picker
    def test_all_five_actual_closed_page_originals_use_independent_pure_contexts_and_frozen_membership(self):
        for index in range(1,6):scope,picker=self.cycle(index)
        with scope.held():self.f.page.close(scope,picker)
        before={str(p):(p.read_bytes(),p.stat().st_ino) for root in self.f.h.roots.values() for p in root.rglob('*') if p.is_file()}
        with ExitStack() as held:
            for scope in self.f.scopes:held.enter_context(scope.held())
            held.enter_context(patch.object(self.f.boundary,'exchange',side_effect=self.forbidden))
            held.enter_context(patch.object(PrivateFeatureState,'write',side_effect=self.forbidden))
            view=RecordingAssetsMetadata(selection=self.f.selected);result=inspect_page(self.context(),metadata=view);report=result['report'];view.guard()
            self.assertTrue(report['normalPageClosed']);self.assertFalse(report['wholeEndEligible']);self.assertFalse(report['abortAuthorized'])
            self.assertEqual(['page-originals'],report['responsibilities']);self.assertTrue(report['paths']<=report['actualOriginalReads'])
            self.assertIsNot(result['owner'],self.f.page);self.assertTrue(result['owner'].historical)
            self.assertTrue(all(result['pickers'][i] is not self.f.pickers[i] for i in range(1,6)))
            frozen=FrozenAssetsMetadata(view.copies,selection=self.f.selected);again=inspect_page(self.context(),metadata=frozen)
            self.assertEqual(report['responsibilities'],again['report']['responsibilities']);self.assertEqual(report['paths'],again['report']['paths'])
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for root in self.f.h.roots.values() for p in root.rglob('*') if p.is_file()})
    def test_completed_single_episode_is_readable_open_prefix_and_never_normal_or_abort_end(self):
        scope,_picker=self.cycle(1)
        with scope.held(),patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            result=inspect_page(self.context());report=result['report']
            self.assertEqual(['page-originals','shared-page-root'],report['responsibilities']);self.assertEqual(1,report['bornEpisodes'])
            self.assertFalse(report['normalPageClosed']);self.assertFalse(report['abortAuthorized']);self.assertFalse(report['wholeEndEligible'])
    def test_planned_source_keeps_actual_prefix_and_child_duties_without_query_or_saved_relabel(self):
        scope=self.f.begin(1,format(1,'032x'))
        with scope.held():
            picker=self.f.picker(scope);intent=self.f.page.originals.intent
            def interrupted(kind,ref):
                result=intent(kind,ref)
                if ref['phase']=='planned':raise NativeUIError('Modeled interruption before page-source original open')
                return result
            with patch.object(self.f.page.originals,'intent',side_effect=interrupted):
                with self.assertRaises(NativeUIError):picker.open_page()
            before=self.f.page.store.path.read_bytes()
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
                result=inspect_page(self.context());report=result['report']
                self.assertIn('page-source-write',report['responsibilities']);self.assertIn('episode-input-files',report['responsibilities'])
                self.assertEqual('planned',result['owner'].state['pending']['original']['phase']);self.assertFalse(report['normalPageClosed'])
            self.assertEqual(before,self.f.page.store.path.read_bytes())
    def test_unknown_parent_namespace_and_same_bytes_foreign_original_inode_fail_pure_inventory(self):
        scope,_picker=self.cycle(1)
        with scope.held():
            unknown=self.f.page.store.path.with_name('assets-page-lease-unknown-owned-lookalike');unknown.write_bytes(b'Unknown');unknown.chmod(0o600)
            with self.assertRaises(NativeUIError):inspect_page(self.context())
            unknown.unlink();ref=self.f.page.state['records'][0];path=self.f.page.originals.path(self.f.page.originals.expand(ref));raw=path.read_bytes()
            path.rename(path.with_name('retained-page-before-foreign-inode'));path.write_bytes(raw);path.chmod(0o600)
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
                with self.assertRaises(NativeUIError):inspect_page(self.context())


if __name__=='__main__':unittest.main()
