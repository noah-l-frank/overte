"""Original normal action1 page opening before any file/picker stage.

Actual original QML executes; native/Qt/file/service boundaries remain models.
These counters supply no device/native/full29 qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_episodes import AssetsEpisodes
from ios.adapters.assets_page_birth import AssetsPageBirth
from ios.adapters.assets_born_page_lease import BornAssetsPageLease
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles
from ios.self_tests.assets_shared_page_client_fixture import Boundary
from ios.self_tests.test_ios_assets_action_phase import AssetsActionPhaseTests
from ios.self_tests.assets_picker_fixture import RUN,BINDING,URL


class AssetsPageBirthTests(unittest.TestCase):
    def setUp(self):
        self.a=AssetsActionPhaseTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        self.root=self.a.h.roots['primary'];self.b=Boundary(self.root);self.addCleanup(self.b.close)
        ticket,row=self.a.activate(1);self.action=self.a.owner.begin(1,ticket,row['verb'],row['inputs'])
        self.store=PrivateFeatureState(self.root/('ios-assets-page-birth-'+RUN+'-primary.json'))
        self.owner=AssetsPageBirth(self.a.selected,self.store,self.a.h.locks['primary'],self.action,self.b.native_input(),self.b.clock_reader,
            monotonic=self.b.monotonic);self.owner.reserve()
        self.episodes=AssetsEpisodes(self.a.selected,self.a.h.locks)
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical root page original cannot acquire/query/write')
    def archived(self):return AssetsPageBirth.from_archive(self.a.selected,self.store,self.a.h.locks['primary'],self.a.owner,monotonic=self.b.monotonic)
    def test_action1_actual_page_opens_without_files_then_episode1_attaches_at_actual_action2_on_same_page(self):
        page=self.owner.open();self.assertTrue(page['alive']);self.assertEqual([],self.b.requests);self.assertEqual([],self.episodes.state['entries'])
        self.assertEqual([],list(self.root.glob('feature-assets-*')));self.assertIsNone(self.a.h.file_store.read())
        page_store=PrivateFeatureState(self.root/('ios-assets-page-lease-'+RUN+'-primary.json'))
        parent=BornAssetsPageLease(self.episodes,page_store,self.a.h.locks['primary'],birth=self.owner,monotonic=self.b.monotonic)
        parent.reserve();self.assertEqual(page,parent.attach_birth());self.a.owner.complete(self.action)
        ticket,row=self.a.activate(2);current=self.a.owner.begin(2,ticket,row['verb'],row['inputs']);scope=self.episodes.begin(1,ticket)
        birth=self.archived();parent=BornAssetsPageLease(self.episodes,page_store,self.a.h.locks['primary'],birth=birth,monotonic=self.b.monotonic)
        with scope.held():
            root=Path(scope.descriptor['directories']['primary']['stateRoot']['path']);lock=scope.locks['primary']
            files=EpisodeAssetsFiles(self.b.files_native(),PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-files.json')),BINDING,RUN,URL,
                lock=lock,selection=self.a.selected,episode=scope);files.reserve(ticket);files.stage()
            picker=PageLeasePicker(self.b.native_input(),files,PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-picker.json')),BINDING,
                lock=lock,page_lease=parent,episode=scope,monotonic=self.b.monotonic,sleep=self.b.sleep);picker.reserve()
            count=len(self.b.inputs);picker.open_page();self.assertEqual(count,len(self.b.inputs));self.assertEqual([],picker.state['inputs'])
            self.assertEqual(page,parent.identity());self.assertEqual(page['rootId'],picker.state['page']);self.assertEqual(2,parent.previous['iosAssetsPageLeaseVersion'])
            self.assertEqual(ticket,files.state['ticket']);self.assertNotEqual(ticket,self.owner.ticket);self.assertTrue(current.guard())
    def test_lost_open_return_recovers_actual_page_without_resending_and_completed_action_replay_is_pure(self):
        self.b.configure(lost='assets.open')
        with self.assertRaises(NativeUIError):self.owner.open()
        count=len(self.b.inputs);self.assertTrue(self.b.host_state['pageAlive']);page=self.owner.open();self.assertEqual(count,len(self.b.inputs))
        self.a.owner.complete(self.action);before={str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.rglob('*') if p.is_file()}
        with patch.object(self.b,'exchange',side_effect=self.forbidden),patch.object(self.a.phase,'status',side_effect=self.forbidden),patch.object(PrivateFeatureState,'write',side_effect=self.forbidden):
            cold=self.archived();self.assertEqual(page,cold.page());self.assertTrue(cold.historical)
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for p in self.root.rglob('*') if p.is_file()});self.assertEqual([],self.b.requests)
    def test_ignored_open_ack_is_not_an_actual_page_or_permission_to_replay(self):
        self.b.configure(ignore='assets.open')
        with self.assertRaises(NativeUIError):self.owner.open()
        count=len(self.b.inputs);self.assertFalse(self.b.host_state['pageAlive'])
        with self.assertRaises(NativeUIError):self.owner.open()
        self.assertEqual(count,len(self.b.inputs));self.assertEqual('opening',self.owner.state['phase']);self.assertIsNone(self.owner.state['openedBy'])
        with self.assertRaises(NativeUIError):self.owner.page()
        self.assertEqual([],self.b.requests);self.assertEqual([],self.episodes.state['entries'])
    def test_samebytes_foreign_native_original_inode_cannot_replay_completed_page_birth(self):
        self.owner.open();self.a.owner.complete(self.action);ref=self.owner.state['frames'][0]
        path=self.owner.originals.path(self.owner.originals.expand(ref));raw=path.read_bytes();path.rename(path.with_name('retained-page-birth-before-foreign-inode'))
        path.write_bytes(raw);path.chmod(0o600)
        with patch.object(self.b,'exchange',side_effect=self.forbidden),patch.object(self.a.phase,'status',side_effect=self.forbidden):
            with self.assertRaises(NativeUIError):self.archived()
        self.assertEqual([],self.b.requests)


if __name__=='__main__':unittest.main()
