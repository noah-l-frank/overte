"""Explicit existing Combined Share/Photos/Return integration and refusal.

Native/Qt/OS/SDK remain declared models. The production owners, ordinary
inputs, host original files, Node process source and cleanup paths execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
import time
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner,_ReturnPage
from ios.adapters.snapshot_share_runtime import IOSSnapshotShareRuntime
from ios.adapters.snapshot_photos_runtime import IOSSnapshotPhotosRuntime
from ios.self_tests.snapshot_combined_return_domain import CombinedShareDomain,CombinedPhotosDomain,CombinedPageReturnFlow
from ios.self_tests import test_ios_snapshot_share_history as history_test,test_ios_snapshot_page_return as return_test


class CombinedReturnContractTests(unittest.TestCase):
    def test_profiles_are_closed_before_sdk_or_session_access(self):
        factories=(IOSSnapshotShareRuntime.share_owner,IOSSnapshotShareRuntime.archive_end_owner,
            IOSSnapshotShareRuntime.page_return_owner,IOSSnapshotPhotosRuntime.photos_owner)
        for factory in factories:
            with self.subTest(factory=factory.__name__),self.assertRaises(NativeUIError):
                args=(object(),'primary','a'*32,None,None) if factory is IOSSnapshotPhotosRuntime.photos_owner else (object(),'primary','a'*32,None,None,None)
                with factory(*args,combined=1):pass
    def test_unowned_combined_return_file_blocks_both_profiles_without_adoption_or_overwrite(self):
        from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups)
        foreign=f.root/'ios-snapshot-combined-return-frame-unowned.json';foreign.write_bytes(b'unknown existing original');foreign.chmod(0o600)
        original=(foreign.stat().st_ino,foreign.read_bytes())
        with f.lock.held():
            for combined in (False,True):
                owner=object.__new__(_ReturnPage);owner.combined=combined
                owner.store=PrivateFeatureState(f.root/'ios-snapshot-return-page-owner.json')
                owner.binding,owner.run,owner.monotonic=f.binding,'a'*32,time.monotonic
                owner.bound=lambda:True;owner.storage_intent=lambda *_:None;owner.frames=owner.frame_store()
                with self.subTest(combined=combined),self.assertRaises(NativeUIError):owner.inventory(dict(records=[],observation=None))
                self.assertFalse(owner.store.path.exists());self.assertEqual(original,(foreign.stat().st_ino,foreign.read_bytes()))

    def test_return_uses_its_own_short_combined_namespace_and_refuses_mixed_parents_before_child_access(self):
        from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
        from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        with f.lock.held():
            readers=[]
            for cls,combined in ((_ReturnPage,False),(_ReturnPage,True),(IOSSnapshotPageOwner,True)):
                owner=object.__new__(cls);owner.combined=combined;owner.store=PrivateFeatureState(f.root/'metadata.json')
                owner.binding,owner.run,owner.monotonic=f.binding,'a'*32,time.monotonic
                owner.bound=lambda:True;owner.storage_intent=lambda kind,value:intents.append(deepcopy(value))
                readers.append(owner.frame_store())
            payload=dict(actualOriginal='same immutable bytes, independent frame owner')
            refs=[reader.write(1,payload) for reader in readers]
            for index,reader in enumerate(readers):
                own=reader.expand(refs[index]);path=reader.path(own);original=(path.stat().st_ino,path.read_bytes())
                self.assertEqual(payload,reader.read(own));self.assertLessEqual(len(reader.namespace),32)
                for foreign,ref in enumerate(refs):
                    if foreign!=index:
                        with self.subTest(reader=index,foreign=foreign),self.assertRaises((NativeUIError,OSError)):reader.read(reader.expand(ref))
                self.assertEqual(original,(path.stat().st_ino,path.read_bytes()))
        page=object.__new__(IOSSnapshotPageOwner);page.historical=True;page.combined=True
        # Unknown children must not be read in order to reinterpret Page2 as
        # the literal Separate1 return profile.
        with self.assertRaises(NativeUIError):SnapshotPageReturnOwner.history(page,object(),object())


class CombinedShareHistoryTests(history_test.SnapshotShareHistoryTests):
    def completed(self,cleanup=False):
        with patch.object(history_test,'SnapshotShareDomain',CombinedShareDomain):d,proof,retired=super().completed(cleanup)
        self.assertEqual(2,proof['iosSnapshotShareTransferVersion'])
        if retired is not None:self.assertEqual(2,retired['iosSnapshotShareCleanupVersion'])
        return d,proof,retired
    def reader(self,domain,**changes):
        changes.setdefault('combined',True);return super().reader(domain,**changes)


class CombinedDestinationTests(unittest.TestCase):
    def test_normal_photos_save_and_once_only_cleanup_keep_capture2_and_original_png(self):
        d=CombinedPhotosDomain(self);path=d.main.f.f.h.path;png=(path.stat().st_ino,path.read_bytes())
        with d.owner() as owner:
            saved=owner.save('7'*32);self.assertEqual(2,saved['iosSnapshotPhotosSavedVersion'])
            self.assertEqual(2,owner.previous['iosSnapshotPhotosOwnerVersion']);self.assertTrue(owner.capture()[0].combined)
            self.assertEqual(png[1],d.helper.run_root.joinpath('original.bytes').read_bytes())
            cleaned=owner.cleanup();self.assertEqual(2,cleaned['iosSnapshotPhotosCleanupVersion'])
            self.assertTrue(cleaned['photosAssetAbsent']);self.assertTrue(cleaned['companionRunFilesAbsent'])
        self.assertEqual(png,(path.stat().st_ino,path.read_bytes()));self.assertFalse(d.library)
        with d.owner() as owner:self.assertEqual(cleaned,owner.cleanup())
        self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))

    def test_denied_or_limited_photos_permission_blocks_combined_save_before_input(self):
        for permission in (2,4):
            with self.subTest(permission=permission):
                d=CombinedPhotosDomain(self);d.helper.authorization=permission
                with d.owner() as owner,self.assertRaises(NativeUIError):owner.save('7'*32)
                self.assertEqual(0,d.save_count);self.assertFalse(d.library)

    def test_lost_combined_normal_save_return_recovers_original_and_cleanup_without_replay(self):
        d=CombinedPhotosDomain(self);d.lose_save=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.save('7'*32)
        with d.owner() as owner:
            saved=owner.save('7'*32);self.assertEqual(2,saved['iosSnapshotPhotosSavedVersion'])
            self.assertTrue(owner.cleanup()['photosAssetAbsent'])
        self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))

    def test_opposite_profile_cannot_dispatch_share_or_save_from_combined_capture(self):
        for kind in ('share','save'):
            d=CombinedShareDomain(self) if kind=='share' else CombinedPhotosDomain(self);d.combined=False
            if kind=='share':d.activate('share-open','1'*32)
            before=deepcopy(d.main.commands)
            with self.subTest(kind=kind),d.owner() as owner,self.assertRaises(NativeUIError):
                owner.open('1'*32) if kind=='share' else owner.save('7'*32)
            self.assertEqual(before,d.main.commands)
            self.assertEqual(0,d.share_count if kind=='share' else d.save_count)

    def test_lost_combined_normal_share_return_recovers_original_delivery_without_replay(self):
        d=CombinedShareDomain(self);d.activate('share-open','1'*32);d.lost_share=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.open('1'*32)
        with d.owner() as owner:owner.open('1'*32)
        self.assertEqual(1,d.share_count);d.activate('share-cancel','3'*32)
        with d.owner() as owner:self.assertTrue(owner.cancel('3'*32)['wholeFeatureRequired'])
        self.assertEqual(1,d.share_count)


class CombinedWholeReturnTests(unittest.TestCase):
    def prepared(self):
        with patch.object(return_test,'PageReturnFlow',CombinedPageReturnFlow):return return_test.SnapshotPageReturnOwnerTests.prepared(self)
    def test_original_combined_page_pending_png_share_archive_end_and_file_cleanup_return_same_main(self):
        d,host=self.prepared();before=(host.stat().st_ino,host.read_bytes())
        with d.return_owner() as owner:
            result=owner.restore();self.assertEqual(2,result['snapshotPageReturnedVersion'])
            self.assertTrue(result['restoration']['originalRouteRestored']);self.assertTrue(result['restoration']['launcherSelectionRestored'])
            self.assertEqual(2,owner.previous['snapshotPageReturnOwnerVersion']);self.assertTrue(owner.engine.combined)
            self.assertTrue(owner.page.combined);self.assertTrue(owner.files.combined);self.assertTrue(owner.end.share.combined)
            self.assertEqual('ios-snapshot-combined-return',owner.engine.frames.namespace)
        self.assertFalse(d.page.shown);self.assertEqual(2,d.page.index);self.assertTrue(d.main_foreground)
        self.assertEqual((1,1),(d.archive.stop_calls,d.archive.delete_calls));clicks=deepcopy(d.page.clicks)
        with d.return_owner() as repeated:self.assertEqual(result,repeated.restore())
        self.assertEqual(clicks,d.page.clicks);self.assertEqual(before,(host.stat().st_ino,host.read_bytes()))
        with (repeated.lock.held(),repeated.end.share.archive_lock.held(),
                patch.object(d.archive,'execute',side_effect=AssertionError('Historical SDK command')),
                patch.object(d.archive,'call',side_effect=AssertionError('Historical SDK read')),
                patch.object(d.primary_ui,'call',side_effect=AssertionError('Historical UIKit read')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical write'))):
            historical=SnapshotPageReturnOwner.history(repeated.page,repeated.files,repeated.end,combined=True)
            self.assertEqual(result,historical.proof())
            with self.assertRaises(NativeUIError):SnapshotPageReturnOwner.history(repeated.page,repeated.files,repeated.end)


if __name__=='__main__':unittest.main()
