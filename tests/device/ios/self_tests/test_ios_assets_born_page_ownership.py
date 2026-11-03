"""Pure page-before-files original ownership with zero/one actual episodes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata,FrozenAssetsMetadata
from ios.adapters.assets_page_birth_ownership import AssetsPageBirthInventoryContext,inspect_birth
from ios.adapters.assets_page_ownership import AssetsPageInventoryContext,inspect_page
from ios.adapters.assets_born_page_lease import BornAssetsPageLease
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles
from ios.self_tests.test_ios_assets_page_birth import AssetsPageBirthTests
from ios.self_tests.assets_picker_fixture import RUN,BINDING,URL


class AssetsBornPageOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.h=AssetsPageBirthTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Pure prefix inventory may not acquire/query/write')
    def context(self):return AssetsPageBirthInventoryContext(self.h.a.selected,self.h.a.owner,self.h.a.h.locks['primary'])
    def parent(self):
        parent=BornAssetsPageLease(self.h.episodes,PrivateFeatureState(self.h.root/('ios-assets-page-lease-'+RUN+'-primary.json')),
            self.h.a.h.locks['primary'],birth=self.h.owner,monotonic=self.h.b.monotonic);parent.reserve();parent.attach_birth();return parent
    def test_opened_but_action_pending_zero_episode_prefix_remains_owned_without_current_native_or_abort_success(self):
        self.h.owner.open();self.parent()
        with patch.object(self.h.b,'exchange',side_effect=self.forbidden),patch.object(self.h.a.phase,'status',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            view=RecordingAssetsMetadata(selection=self.h.a.selected);birth=inspect_birth(self.context(),metadata=view);view.guard()
            self.assertFalse(birth['report']['action1Complete']);self.assertIn('page-action-completion',birth['report']['responsibilities'])
            self.assertTrue(birth['report']['originalPage']['alive']);self.assertFalse(birth['report']['currentNativeFactsProduced'])
            page=inspect_page(AssetsPageInventoryContext(self.h.episodes,(),birth['owner']))['report']
            self.assertEqual(0,page['bornEpisodes']);self.assertEqual(['page-originals','shared-page-root'],page['responsibilities'])
            self.assertFalse(page['normalPageClosed']);self.assertFalse(page['abortAuthorized']);self.assertFalse(page['wholeEndEligible'])
        self.assertEqual([],self.h.b.requests)
    def test_actual_action2_attachment_reads_page2_under_independent_historical_birth_and_frozen_metadata(self):
        self.h.owner.open();self.parent();self.h.a.owner.complete(self.h.action)
        ticket,row=self.h.a.activate(2);self.h.a.owner.begin(2,ticket,row['verb'],row['inputs']);scope=self.h.episodes.begin(1,ticket)
        parent=BornAssetsPageLease(self.h.episodes,PrivateFeatureState(self.h.root/('ios-assets-page-lease-'+RUN+'-primary.json')),
            self.h.a.h.locks['primary'],birth=self.h.archived(),monotonic=self.h.b.monotonic)
        with scope.held():
            root=Path(scope.descriptor['directories']['primary']['stateRoot']['path']);lock=scope.locks['primary']
            files=EpisodeAssetsFiles(self.h.b.files_native(),PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-files.json')),BINDING,RUN,URL,
                lock=lock,selection=self.h.a.selected,episode=scope);files.reserve(ticket);files.stage()
            picker=PageLeasePicker(self.h.b.native_input(),files,PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-picker.json')),BINDING,
                lock=lock,page_lease=parent,episode=scope,monotonic=self.h.b.monotonic,sleep=self.h.b.sleep);picker.reserve();picker.open_page()
            before={str(p):(p.read_bytes(),p.stat().st_ino) for p in self.h.root.rglob('*') if p.is_file()}
            with patch.object(self.h.b,'exchange',side_effect=self.forbidden),patch.object(self.h.a.phase,'status',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
                view=RecordingAssetsMetadata(selection=self.h.a.selected);birth=inspect_birth(self.context(),metadata=view)
                first=inspect_page(AssetsPageInventoryContext(self.h.episodes,(scope,),birth['owner']),metadata=view);view.guard()
                frozen=FrozenAssetsMetadata(view.copies,selection=self.h.a.selected);old=inspect_birth(self.context(),metadata=frozen)
                again=inspect_page(AssetsPageInventoryContext(self.h.episodes,(scope,),old['owner']),metadata=frozen)
                self.assertTrue(birth['report']['action1Complete']);self.assertEqual(first['report']['responsibilities'],again['report']['responsibilities'])
                self.assertEqual(first['report']['paths'],again['report']['paths']);self.assertFalse(first['report']['wholeEndEligible'])
            self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for p in self.h.root.rglob('*') if p.is_file()})
    def test_lost_native_after_keeps_returned_UI_prefix_without_requery_or_complete_frame_relabel(self):
        actual=self.h.b.clock_reader.read;calls=0
        def lost(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('Modeled native-after loss after actual UI return')
            return actual(*args,**kwargs)
        with patch.object(self.h.b.clock_reader,'read',side_effect=lost):
            with self.assertRaises(OSError):self.h.owner.open()
        before=self.h.store.path.read_bytes();self.assertIsNotNone(self.h.owner.state['pending']['ui'])
        with patch.object(self.h.b,'exchange',side_effect=self.forbidden),patch.object(self.h.a.phase,'status',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            result=inspect_birth(self.context());self.assertIn('page-birth-source-write',result['report']['responsibilities'])
            self.assertIn('page-birth-inputs',result['report']['responsibilities']);self.assertIsNone(result['report']['originalPage'])
        self.assertEqual(before,self.h.store.path.read_bytes());self.assertEqual(2,calls);self.assertEqual([],self.h.b.requests)
    def test_foreign_birth_ticket_and_unknown_original_namespace_cannot_inherit_current_action_authority(self):
        self.h.owner.open();self.h.a.owner.complete(self.h.action);value=deepcopy(self.h.owner.previous);value['action']['ticket']='f'*32
        self.h.store.write(value,self.h.owner.previous)
        try:
            with patch.object(self.h.b,'exchange',side_effect=self.forbidden),patch.object(self.h.a.phase,'status',side_effect=self.forbidden):
                with self.assertRaises(NativeUIError):inspect_birth(self.context())
        finally:self.h.store.write(self.h.owner.previous,value)
        path=self.h.root/'assets-page-birth-foreign-owned-lookalike';path.write_bytes(b'Actual unknown');path.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_birth(self.context())
        self.assertEqual([],self.h.b.requests)


if __name__=='__main__':unittest.main()
