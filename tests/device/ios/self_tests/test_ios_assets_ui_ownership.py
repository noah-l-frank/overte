"""Actual current/failed/interrupted UI originals under pure historical replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.assets_ui_ownership import AssetsUiInventoryContext,inspect_ui
from ios.adapters import assets_ui_ownership as ui_inventory
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata,FrozenAssetsMetadata
from ios.self_tests.assets_ui_screen_fixture import UiFixture,TICKET

LATER='e'*32


class AssetsUiOwnershipTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.f=UiFixture(self,self.root)
    def authority(self,ticket=LATER):
        return AssetsUiInventoryContext(self.root,self.f.artifacts,self.f.source.binding,self.f.source.run,'browse',
            self.f.subject,ticket,self.f.policy,self.f.f.lock,self.f.upload,self.f.marker)
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Historical UI inventory may not acquire, write or retire')
    def pure(self):
        return (patch.object(self.f.b,'exchange',side_effect=self.forbidden),patch.object(self.f.b.native_clock,'send',side_effect=self.forbidden),
            patch.object(PrivateFeatureState,'write',side_effect=self.forbidden))
    def test_current_later_ticket_qualifies_without_changing_upload_or_marker_birth_and_frozen_reader_has_actual_membership(self):
        marker=self.f.marker.previous;self.f.display_ticket=LATER;owner=self.f.samples();ref=owner.capture(LATER);owner.cleanup_files()
        self.assertEqual(TICKET,self.f.f.files.state['ticket']);self.assertEqual(TICKET,self.f.marker.scope.ticket);self.assertEqual(marker,self.f.marker.previous)
        foreign=self.root/'foreign-artifact-authority';foreign.mkdir(mode=0o700)
        files={str(p):(p.stat().st_ino,p.read_bytes()) for p in self.root.rglob('*') if p.is_file()};view=RecordingAssetsMetadata()
        a,b,c=self.pure()
        with a,b,c:
            report=inspect_ui(self.authority(),metadata=view);view.guard()
            self.assertTrue(report['images'][0]['qualified']);self.assertEqual(LATER,report['images'][0]['measurement']['ticket'])
            self.assertEqual(['ui-screen-originals'],report['responsibilities']);self.assertFalse(report['wholeEndEligible'])
            self.assertTrue(report['paths']<=report['actualOriginalReads'])
            frozen=FrozenAssetsMetadata(view.copies);again=inspect_ui(self.authority(),metadata=frozen)
            self.assertEqual(report['images'],again['images']);self.assertEqual(report['paths'],again['paths'])
            with self.assertRaises(NativeUIError):inspect_ui(replace(self.authority(),ticket='f'*32))
            with self.assertRaises(NativeUIError):inspect_ui(replace(self.authority(),artifact_root=foreign))
        self.assertEqual(files,{str(p):(p.stat().st_ino,p.read_bytes()) for p in self.root.rglob('*') if p.is_file()});self.assertEqual(1,len(self.f.gets))
    def test_actual_stale_original_PNG_remains_read_owned_but_never_current_checkpoint_success(self):
        owner=self.f.samples()
        with self.assertRaises(MarkerNotReady):owner.capture(LATER)
        owner.cleanup_files();a,b,c=self.pure()
        with a,b,c:
            report=inspect_ui(self.authority());self.assertFalse(report['images'][0]['qualified'])
            self.assertIn('ui-image-checkpoint',report['responsibilities']);self.assertNotIn('ui-screen-files',report['responsibilities'])
            self.assertTrue(report['paths']<=report['actualOriginalReads'])
        self.assertEqual(1,len(self.f.gets))
    def test_actual_PNG_then_lost_native_after_keeps_partial_byte_membership_and_files_without_query_or_GET_replay(self):
        calls=0
        def clock():
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('Modeled lost native-after return after original PNG')
            return self.f.native_clock()
        owner=self.f.samples(clock);self.f.display_ticket=LATER
        with self.assertRaises((OSError,NativeUIError)):owner.capture(LATER)
        a,b,c=self.pure()
        with a,b,c:
            report=inspect_ui(self.authority());self.assertEqual([],report['images'])
            self.assertIn('ui-screen-acquisition',report['responsibilities']);self.assertIn('ui-screen-files',report['responsibilities'])
            self.assertTrue(report['paths']<=report['actualOriginalReads'])
        self.assertEqual(1,len(self.f.gets));self.assertEqual(2,calls)
    def test_unknown_UI_namespace_and_same_byte_replaced_original_inode_fail_without_new_sources(self):
        self.f.display_ticket=LATER;owner=self.f.samples();owner.capture(LATER);owner.cleanup_files()
        unknown=self.f.artifacts/'assets-ui-unrecognized-owned-lookalike.bin';unknown.write_bytes(b'Unknown actual file');unknown.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_ui(self.authority())
        unknown.unlink();ref=self.f.source.raws.refs[0];path=self.f.source.raws.store.path(self.f.source.raws.store.expand(ref));raw=path.read_bytes()
        path.rename(path.with_name('retained-native-original-before-foreign-inode'));path.write_bytes(raw);path.chmod(0o600)
        a,b,c=self.pure()
        with a,b,c:
            with self.assertRaises(NativeUIError):inspect_ui(self.authority())
        self.assertEqual(1,len(self.f.gets))

    def test_empty_artifact_birth_and_state_require_private_roots_before_original_metadata_read(self):
        self.assertEqual([],list(self.f.artifacts.iterdir()))
        for path in (self.root,self.f.artifacts):
            path.chmod(0o755)
            try:
                with self.assertRaises(NativeUIError):self.authority()
            finally:path.chmod(0o700)
        context=self.authority();original=self.f.artifacts.with_name('retained-empty-screen-root')
        self.f.artifacts.rename(original);self.f.artifacts.mkdir(mode=0o700)
        try:
            with patch.object(PrivateFeatureState,'read',side_effect=self.forbidden):
                with self.assertRaises(NativeUIError):inspect_ui(context)
        finally:
            self.f.artifacts.rmdir();original.rename(self.f.artifacts)
        self.assertEqual([],self.f.gets)

    def test_private_directory_mode_rechecked_after_complete_original_inventory(self):
        self.f.display_ticket=LATER;owner=self.f.samples();owner.capture(LATER);owner.cleanup_files();context=self.authority()
        original=ui_inventory.metadata_entries;root_calls=0
        def entries(directory,metadata):
            nonlocal root_calls
            result=original(directory,metadata)
            if directory==self.f.artifacts:
                root_calls+=1
                if root_calls==2:self.f.artifacts.chmod(0o755)
            return result
        try:
            a,b,c=self.pure()
            with a,b,c,patch.object(ui_inventory,'metadata_entries',side_effect=entries):
                with self.assertRaises(NativeUIError):inspect_ui(context)
            self.assertEqual(2,root_calls)
        finally:self.f.artifacts.chmod(0o700)
        self.assertEqual(1,len(self.f.gets))


if __name__=='__main__':unittest.main()
